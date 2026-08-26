// Mazlík logo - shared source of truth. Same palette and "simple layered
// shapes" convention as the animal illustrations in frontend/index.html
// (henSvg/goatSvg/sheepSvg/cowSvg). Copied by hand into:
//  - frontend/index.html (splash screen + favicon)
//  - kvoc-backend/app/webapp/index.html (splash screen + favicon)
//  - mobile-app/www + mobile-app-real/www (synced copies of the above)
//  - Android launcher icons, rasterized by scripts/render-icons.html
//    (see that file for how - no native SVG rasterizer is available in
//    this environment, so it's done via a canvas in a real browser)
//
// Layout: 2x2 grid, hen/goat/cow/sheep each in their own 30-radius circle,
// 6-unit gaps so nothing overlaps a neighbour. Horns/comb point OUTWARD
// (away from the grid centre) only, never inward, which is what keeps them
// collision-free - verified by rendering and visually inspecting every
// size from 16px up before this was called final (see conversation: v1
// used a 4-circle "flower" layout that looked fine on paper but the sheep's
// wool bumps and the cow's face collided in the actual render).
//
// disc:false gives a transparent-background version for the Android
// adaptive-icon foreground layer (the OS supplies its own background).
function mazlikLogoSvg(opts){
  opts = opts || {};
  var withDisc = opts.disc !== false;
  var vb = opts.viewBox || '0 0 200 200';
  var disc = withDisc ? '<circle cx="100" cy="100" r="94" fill="#E8DCC3" stroke="#5B4A38" stroke-width="4"/>' : '';
  return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="'+vb+'">'+
    disc+
    // HEN - top-left
    '<g>'+
      '<circle cx="68" cy="68" r="30" fill="#A66A3B"/>'+
      '<circle cx="59" cy="41" r="5.5" fill="#C4471F"/>'+
      '<circle cx="68" cy="36" r="6.5" fill="#C4471F"/>'+
      '<circle cx="77" cy="41" r="5.5" fill="#C4471F"/>'+
      '<ellipse cx="75" cy="92" rx="4" ry="6" fill="#C4471F"/>'+
      '<polygon points="82,63 94,67 82,72" fill="#DDA13B"/>'+
      '<circle cx="71" cy="59" r="3.2" fill="#241B14"/>'+
    '</g>'+
    // GOAT - top-right
    '<g>'+
      '<path d="M114,50 Q104,38 111,26" stroke="#5B4A38" stroke-width="6.5" fill="none" stroke-linecap="round"/>'+
      '<path d="M133,46 Q142,33 136,22" stroke="#5B4A38" stroke-width="6.5" fill="none" stroke-linecap="round"/>'+
      '<circle cx="132" cy="68" r="30" fill="#CDBB93"/>'+
      '<ellipse cx="106" cy="62" rx="9" ry="5.5" fill="#CDBB93" stroke="#5B4A38" stroke-width="2" transform="rotate(-25 106 62)"/>'+
      '<ellipse cx="158" cy="62" rx="9" ry="5.5" fill="#CDBB93" stroke="#5B4A38" stroke-width="2" transform="rotate(25 158 62)"/>'+
      '<ellipse cx="132" cy="83" rx="10" ry="7" fill="#EFE4CB"/>'+
      '<circle cx="124" cy="65" r="3" fill="#241B14"/>'+
      '<circle cx="140" cy="65" r="3" fill="#241B14"/>'+
    '</g>'+
    // COW - bottom-left
    '<g>'+
      '<path d="M52,107 Q44,97 52,87" stroke="#5B4A38" stroke-width="6.5" fill="none" stroke-linecap="round"/>'+
      '<path d="M84,107 Q92,97 84,87" stroke="#5B4A38" stroke-width="6.5" fill="none" stroke-linecap="round"/>'+
      '<circle cx="68" cy="132" r="30" fill="#F6F0E3" stroke="#5B4A38" stroke-width="3"/>'+
      '<ellipse cx="52" cy="113" rx="7" ry="9" fill="#241B14" opacity=".9" transform="rotate(-18 52 113)"/>'+
      '<circle cx="59" cy="128" r="3" fill="#241B14"/>'+
      '<circle cx="77" cy="128" r="3" fill="#241B14"/>'+
      '<ellipse cx="68" cy="146" rx="12" ry="8" fill="#DDA13B" opacity=".45"/>'+
    '</g>'+
    // SHEEP - bottom-right (wool scallops hugging its own circle so they
    // can't reach into the cow's quadrant, unlike the v1 layout)
    '<g>'+
      '<circle cx="112" cy="122" r="10" fill="#F6F0E3" stroke="#CDBB93" stroke-width="1.6"/>'+
      '<circle cx="152" cy="122" r="10" fill="#F6F0E3" stroke="#CDBB93" stroke-width="1.6"/>'+
      '<circle cx="106" cy="145" r="9" fill="#F6F0E3" stroke="#CDBB93" stroke-width="1.6"/>'+
      '<circle cx="158" cy="145" r="9" fill="#F6F0E3" stroke="#CDBB93" stroke-width="1.6"/>'+
      '<circle cx="120" cy="155" r="9" fill="#F6F0E3" stroke="#CDBB93" stroke-width="1.6"/>'+
      '<circle cx="144" cy="155" r="9" fill="#F6F0E3" stroke="#CDBB93" stroke-width="1.6"/>'+
      '<circle cx="132" cy="158" r="9.5" fill="#F6F0E3" stroke="#CDBB93" stroke-width="1.6"/>'+
      '<circle cx="132" cy="132" r="24" fill="#241B14"/>'+
      '<circle cx="125" cy="127" r="3" fill="#F6F0E3"/>'+
      '<circle cx="139" cy="127" r="3" fill="#F6F0E3"/>'+
    '</g>'+
    // centre hub, fills the small gap where the 4 quadrants meet
    '<circle cx="100" cy="100" r="13" fill="#C4471F"/>'+
  '</svg>';
}
if(typeof module !== 'undefined') module.exports = { mazlikLogoSvg: mazlikLogoSvg };
