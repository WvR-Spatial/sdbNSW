-- Pandoc filter for the two outputs built from paper.md.
--
--   HTML (docs/index.html): keeps the .web-only blocks, drops .pdf-only,
--   inserts the paper's title block at #paper-start, shifts headings down one
--   level (the page title is the h1) and numbers the sections.
--
--   Typst (the PDF): drops .web-only, keeps .pdf-only, numbers the sections,
--   and writes figures and tables as raw Typst floats that span both columns.
--
-- Run after --citeproc, so that citations inside table cells and captions are
-- already text.

local is_html = FORMAT:match("html") ~= nil
local is_typst = FORMAT:match("typst") ~= nil

local function has_class(el, c)
  return el.classes and el.classes:includes(c)
end

local function typst_inline(blocks)
  -- Render blocks as Typst markup suitable for a content block [...].
  local doc = pandoc.Pandoc(blocks)
  local out = pandoc.write(doc, "typst-citations")
  out = out:gsub("%s+$", "")
  return out
end

local function cell_blocks(cell)
  return cell.contents
end

-- Figures ------------------------------------------------------------------

local function typst_figure(fig)
  local img
  pandoc.walk_block(fig, { Image = function(i) img = i end })
  if not img then return nil end
  local src = img.src:gsub("^figures/", "/docs/figures/")
  local caption = typst_inline(fig.caption.long)
  local raw = string.format(
    '#figure(\n  image("%s", width: 100%%),\n  placement: top, scope: "parent",\n  caption: [%s],\n)',
    src, caption)
  return pandoc.RawBlock("typst", raw)
end

-- Tables -------------------------------------------------------------------

local function is_group_row(row)
  -- A row whose cells after the first are all empty is a group heading.
  for i, cell in ipairs(row.cells) do
    if i > 1 and #cell.contents > 0 then return false end
  end
  return true
end

local function typst_table(tbl, cols)
  local ncol = #tbl.colspecs
  cols = cols or ("(auto," .. string.rep(" 1fr,", ncol - 1) .. ")")
  local parts = {}
  local function add(s) parts[#parts + 1] = s end
  add("table(")
  add("  columns: " .. cols .. ",")
  add("  align: left + top,")
  add("  stroke: none,")
  add("  inset: (x: 3.5pt, y: 2.6pt),")
  add("  table.hline(stroke: 0.7pt),")
  local head = {}
  for _, row in ipairs(tbl.head.rows) do
    for _, cell in ipairs(row.cells) do
      local txt = typst_inline(cell_blocks(cell))
      if txt == "" then head[#head + 1] = "[]" else head[#head + 1] = "[*" .. txt .. "*]" end
    end
  end
  add("  table.header(" .. table.concat(head, ", ") .. "),")
  add("  table.hline(stroke: 0.4pt),")
  for _, body in ipairs(tbl.bodies) do
    for _, row in ipairs(body.body) do
      if is_group_row(row) and #row.cells > 1 then
        add(string.format("  table.cell(colspan: %d, inset: (top: 5pt, bottom: 2pt))[%s],",
          ncol, typst_inline(cell_blocks(row.cells[1]))))
      else
        local cells = {}
        for _, cell in ipairs(row.cells) do
          cells[#cells + 1] = "[" .. typst_inline(cell_blocks(cell)) .. "]"
        end
        add("  " .. table.concat(cells, ", ") .. ",")
      end
    end
  end
  add("  table.hline(stroke: 0.7pt),")
  add(")")
  local caption = typst_inline(tbl.caption.long)
  return pandoc.RawBlock("typst", string.format(
    '#figure(\n  placement: top, scope: "parent", kind: table,\n  caption: [%s],\n  %s\n)',
    caption, table.concat(parts, "\n  ")))
end

-- Section numbers ------------------------------------------------------------

local function number_sections(blocks)
  local n1, n2 = 0, 0
  local numbered_parent = false
  return blocks:walk({
    Header = function(h)
      if h.level == 1 then
        if has_class(h, "unnumbered") then
          numbered_parent = false
          return h
        end
        n1, n2 = n1 + 1, 0
        numbered_parent = true
        h.content:insert(1, pandoc.Space())
        h.content:insert(1, pandoc.Span({ pandoc.Str(tostring(n1)) }, { class = "secno" }))
        return h
      elseif h.level == 2 and numbered_parent and not has_class(h, "unnumbered") then
        n2 = n2 + 1
        h.content:insert(1, pandoc.Space())
        h.content:insert(1, pandoc.Span({ pandoc.Str(n1 .. "." .. n2) }, { class = "secno" }))
        return h
      end
    end,
  })
end

-- Paper title block for the web page -----------------------------------------

local function paper_head(meta)
  local blocks = pandoc.Blocks({})
  local title = pandoc.Header(2, meta.title, { id = "paper", class = "paper-title unlisted unnumbered" })
  blocks:insert(title)
  local by = pandoc.Inlines({})
  by:extend(meta.author)
  by:insert(pandoc.Str(", "))
  by:extend(meta.affiliation)
  blocks:insert(pandoc.Div({ pandoc.Para(by) }, { class = "paper-byline" }))
  local abs = pandoc.Blocks({ pandoc.Header(3, "Abstract", { class = "unnumbered unlisted" }) })
  abs:extend(meta.abstract)
  local kw = pandoc.Inlines({ pandoc.Strong("Keywords."), pandoc.Space() })
  kw:extend(meta.keywords)
  abs:insert(pandoc.Para(kw))
  blocks:insert(pandoc.Div(abs, { class = "abstract" }))
  return blocks
end

-- Keep a number with its unit ------------------------------------------------

local UNITS = { ["m"] = true, ["km"] = true, ["km²"] = true, ["nm"] = true, ["mm"] = true,
  ["s"] = true, ["m⁻¹"] = true, ["MB"] = true }

local function is_unit(text)
  local core = text:gsub("[%.,;:%)%]]+$", "")
  return UNITS[core] == true
end

function Inlines(inl)
  for i = 2, #inl - 1 do
    local a, sp, b = inl[i - 1], inl[i], inl[i + 1]
    if sp.t == "Space" and a.t == "Str" and b.t == "Str" and a.text:match("%d$") and is_unit(b.text) then
      inl[i] = pandoc.Str("\u{00A0}")
    end
  end
  return inl
end

-- Main ---------------------------------------------------------------------

function Pandoc(doc)
  local meta = doc.meta
  local out = pandoc.Blocks({})

  -- 1. Keep or drop the format-specific blocks; place the paper head.
  local function filter(blocks)
    local kept = pandoc.Blocks({})
    for _, b in ipairs(blocks) do
      if b.t == "Div" and has_class(b, "web-only") and not is_html then
        -- dropped
      elseif b.t == "Div" and has_class(b, "pdf-only") and is_html then
        -- dropped
      elseif b.t == "Div" and b.identifier == "paper-start" then
        if is_html then kept:extend(paper_head(meta)) end
      else
        kept:insert(b)
      end
    end
    return kept
  end
  local blocks = filter(doc.blocks)

  -- 2. Number sections (before any heading shift).
  blocks = number_sections(blocks)

  -- 3. Format-specific rewriting.
  if is_typst then
    blocks = blocks:walk({
      Div = function(d)
        if has_class(d, "table-wide") then
          local cols = d.attributes["cols"]
          local res = pandoc.Blocks({})
          for _, b in ipairs(d.content) do
            if b.t == "Table" then res:insert(typst_table(b, cols)) else res:insert(b) end
          end
          return res
        elseif has_class(d, "pdf-only") or has_class(d, "web-only") then
          return d.content
        end
      end,
      Figure = typst_figure,
    })
  elseif is_html then
    blocks = blocks:walk({
      Header = function(h)
        if not has_class(h, "paper-title") and h.level < 6 then
          h.level = h.level + 1
        end
        return h
      end,
      Table = function(t)
        for i, spec in ipairs(t.colspecs) do
          t.colspecs[i] = { spec[1], nil }
        end
        return pandoc.Div({ t }, { class = "table-scroll" })
      end,
      Figure = function(f)
        -- Link each figure to its full-resolution file, for zooming on phones.
        return f:walk({
          Image = function(i)
            i.attributes["loading"] = "lazy"
            return pandoc.Link({ i }, i.src, "", { class = "zoom" })
          end,
        })
      end,
    })
  end

  doc.blocks = blocks
  return doc
end
