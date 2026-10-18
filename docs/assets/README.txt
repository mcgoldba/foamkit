FoamKit logo kit  -  "A Pythonic interface to OpenFOAM"
=======================================================
svg/  (vector, text outlined to paths - no fonts needed)
  foamkit-logo-{light,dark,mono}.svg      mark + wordmark + tagline (README / docs header)
  foamkit-mark-{light,dark,mono}.svg      mark only, full detail (large sizes)
  foamkit-mark-small-*.svg                simplified mark for sizes <= 48 px
  foamkit-avatar.svg                      mark on dark rounded tile (GitHub / PyPI / social avatar)
  foamkit-favicon.svg                     simplified mark on tile (favicon)
  foamkit-social-preview.svg              1280x640 GitHub social preview
png/
  favicon.ico, favicon-{16,32,48}.png, apple-touch-icon-180.png
  foamkit-logo-{light,dark}.png, foamkit-mark-{light,dark}-512.png, foamkit-avatar-512.png
  foamkit-social-preview.png              upload under repo Settings > Social preview

Palette: deep blue #0F3F66  blue #1E78B4 (sky #5FB4E6 on dark)  dark green #1B7A4B (#2A9D63 on dark)  orange #F28C28  dark bg #0C2238  paper #F6FAF6
Type:    Sora Bold (wordmark), JetBrains Mono (tagline) - both SIL OFL.
README snippet (auto light/dark):
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="foamkit-logo-dark.svg">
    <img alt="FoamKit" src="foamkit-logo-light.svg" width="420">
  </picture>
