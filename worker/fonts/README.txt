Caption display fonts for REBUILD R-19. All SIL Open Font License 1.1 (each OFL.txt ships
next to its fonts; none declares a Reserved Font Name). Source: github.com/google/fonts
ofl/<family>/ at commit 23e54b51ddffbc7713c583748e3bd86f62b1fa4a (2026-09-29).
The Dockerfile copies this directory to /usr/share/fonts/truetype/clipflow/.

Family names for ASS "Style:" / fontconfig (from fc-scan):
  Anton            Regular                  anton/Anton-Regular.ttf            static
  Bebas Neue       Regular                  bebas-neue/BebasNeue-Regular.ttf   static
  Archivo Black    Regular                  archivo-black/ArchivoBlack-Regular.ttf static
  Poppins          Bold, ExtraBold          poppins/Poppins-{Bold,ExtraBold}.ttf static
  Montserrat       Bold, ExtraBold, Black   montserrat/Montserrat[wght].ttf    VARIABLE (named instances)
  Oswald           Bold (wght 200-700)      oswald/Oswald[wght].ttf            VARIABLE (named instances)
  Inter            Bold, Black              inter/Inter[opsz,wght].ttf         VARIABLE (named instances)

google/fonts ships Montserrat, Oswald and Inter only as variable fonts. Before relying on
their weights, render a frame per weight: libass must pick the named instance, not the
default (Regular). If it doesn't, cut static instances with fontTools varLib.instancer
(allowed by OFL; no Reserved Font Name to rename around).

sha256:
  a4ba3a92350ebb031da0cb47630ac49eb265082ca1bc0450442f4a83ab947cab  anton/Anton-Regular.ttf
  dd9a89a019b4849f66ab75455fe7bdf931311042cbb0f0f97acc061539703180  archivo-black/ArchivoBlack-Regular.ttf
  08e4623805102d819f58601e46e345648846075e363b2ceb23313c2d1c83ec73  bebas-neue/BebasNeue-Regular.ttf
  29160a80ff49ddcab2c97711247e08b1fab27a484a329ce8b813d820dc559031  inter/Inter[opsz,wght].ttf
  0f7b311b2f3279e4eef9b2f968bcdbab6e28f4daeb1f049f4f278a902bcd82f7  montserrat/Montserrat[wght].ttf
  5b38c246e255a12f5712d640d56bcced0472466fc68983d2d0410ec0457c2817  oswald/Oswald[wght].ttf
  983676516167748b74de6f4771fb384c664fd913acb8b471122ecacf5da5ea6c  poppins/Poppins-Bold.ttf
  f2ab17c1a63a0ecc12c2461848fc8a469395e3cd2d641803e889c643d9f958e1  poppins/Poppins-ExtraBold.ttf
