# LaTeX Preamble

LaTeX packages and commands injected into the PDF compilation. Parsed by
`infrastructure/rendering/latex_utils.py` and combined by the PDF renderer before
the final Pandoc/XeLaTeX pass.

```latex
% Core mathematics
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{amsfonts}

% Document layout
\makeatletter
\@ifpackageloaded{geometry}
  {\geometry{top=0.50in,bottom=0.55in,left=0.55in,right=0.55in,includeheadfoot}}
  {\usepackage[top=0.50in,bottom=0.55in,left=0.55in,right=0.55in,includeheadfoot]{geometry}}
\makeatother
\usepackage{float}
\usepackage{graphicx}

% Tables
\usepackage{booktabs}
\usepackage{longtable}
\usepackage{array}

% Code listings (DSPy-style signatures appear as code blocks)
\usepackage{listings}

% Typography and formatting
\usepackage{microtype}
\usepackage{xcolor}

% Cross-references and citations
\makeatletter
\@ifpackageloaded{hyperref}
  {\hypersetup{colorlinks=true,linkcolor=red,urlcolor=red,citecolor=red,anchorcolor=red,filecolor=red}}
  {\usepackage{hyperref}\hypersetup{colorlinks=true,linkcolor=red,urlcolor=red,citecolor=red,anchorcolor=red,filecolor=red}}
\makeatother
\usepackage[capitalise,noabbrev]{cleveref}
\usepackage{natbib}
```
