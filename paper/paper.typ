// Pandoc template for the conference-layout PDF: two columns on A4, with the
// title, author and abstract across both. Figures and tables arrive from the
// filter (build.lua) as floats that span both columns.

#let blockquote(body) = block(inset: (left: 1.2em, top: 0.2em, bottom: 0.2em), text(size: 0.95em, body))
#let horizontalrule = line(length: 100%, stroke: 0.4pt)

#let ink = rgb("#1b2430")
#let muted = rgb("#5a6472")
#let accent = rgb("#1d5a8c")

#set document(title: [$title$], author: "$author$", date: none)
#set page(
  paper: "a4",
  margin: (x: 16mm, top: 19mm, bottom: 20mm),
  columns: 2,
  header: context {
    if counter(page).get().first() > 1 {
      set text(font: "Inter", size: 6.8pt, fill: muted)
      [Van Ryn #h(1fr) Satellite-derived bathymetry on an exposed temperate coast]
      v(-1.5mm)
      line(length: 100%, stroke: 0.3pt + muted)
    }
  },
  footer: context {
    set text(font: "Inter", size: 6.8pt, fill: muted)
    if counter(page).get().first() == 1 {
      [Version 1.0, $date$. Not peer reviewed. Text and figures CC BY 4.0. #h(1fr) #counter(page).display()]
    } else {
      h(1fr); counter(page).display(); h(1fr)
    }
  },
)
#set columns(gutter: 6mm)
#set text(font: "Libertinus Serif", size: 9.6pt, fill: ink, lang: "en", region: "AU", hyphenate: true)
#set par(justify: true, leading: 0.56em, spacing: 0.78em)
#show link: set text(fill: accent)

#show heading: set text(font: "Inter", fill: ink)
#show heading.where(level: 1): it => block(above: 1.25em, below: 0.65em, sticky: true,
  text(size: 9.4pt, weight: "semibold", it.body))
#show heading.where(level: 2): it => block(above: 1.0em, below: 0.5em, sticky: true,
  text(size: 8.6pt, weight: "medium", style: "italic", it.body))
#show heading.where(level: 3): it => block(above: 0.9em, below: 0.45em, sticky: true,
  text(size: 8.6pt, weight: "regular", style: "italic", it.body))

#show figure: set block(spacing: 1.1em)
#show figure: set place(clearance: 1.1em)
#show figure.caption: set text(size: 7.9pt)
#show figure.caption: set align(left)
#show figure.caption: set par(justify: false, leading: 0.5em)
#show figure.where(kind: table): set figure.caption(position: top)
#show figure.where(kind: table): set figure(gap: 0.7em)
#show table: set text(font: "Inter", size: 6.9pt)
#show table: set par(justify: false, leading: 0.45em)
#show table: set text(hyphenate: false)
#set figure(numbering: none)

#show list: set par(justify: false)
#set list(indent: 0.3em, body-indent: 0.5em, spacing: 0.5em)

// The reference list from citeproc.
#show <refs>: set text(size: 8.1pt)
#show <refs>: set par(justify: false, hanging-indent: 1.2em, leading: 0.45em, spacing: 0.55em)

// Title block across both columns.
#place(top, scope: "parent", float: true, clearance: 7mm)[
  #set par(justify: false)
  #block(below: 4.5mm)[
    #text(font: "Inter", size: 15.5pt, weight: "semibold", fill: ink)[$title$]
  ]
  #text(font: "Inter", size: 9.4pt, weight: "medium")[$author$] \
  #text(font: "Inter", size: 8.2pt, fill: muted)[$affiliation$ · #link("mailto:$email$")[$email$]]
  #v(1.2mm)
  #text(font: "Inter", size: 7.6pt, fill: muted)[Web version: #link("$weburl$")[$weburl$] · Code, protocols and outputs: #link("$repo$")[$repo$]]
  #v(4mm)
  #block(width: 100%, inset: (x: 0mm, y: 3.2mm), stroke: (top: 0.6pt + ink, bottom: 0.6pt + ink))[
    #set text(size: 9pt)
    #set par(justify: true, leading: 0.52em)
    #text(font: "Inter", size: 8pt, weight: "semibold")[Abstract] \
    $abstract$

    #text(size: 8.4pt)[*Keywords:* $keywords$]
  ]
]

$body$
