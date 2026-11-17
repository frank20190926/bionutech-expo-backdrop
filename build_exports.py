#!/usr/bin/env python3
"""Rebuild live-text SVGs, path-only CMYK PDFs and verified delivery archive.
Requires existing Pillow, fontTools and PyMuPDF. No network or package installation.
"""
from pathlib import Path
from io import BytesIO
import base64, html, json, math, zipfile, zlib
from PIL import Image, ImageCms
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.pens.basePen import BasePen
import fitz
ROOT=Path(__file__).resolve().parent; OUT=ROOT/'exports'; OUT.mkdir(exist_ok=True)
G='#1B5E20'; B='#6D4224'; GOLD='#B8A365'; INK='#263E2C'; CREAM='#F5F2E7'
CMYK={G:(.82,.35,.88,.28),B:(.32,.64,.84,.26),GOLD:(.18,.28,.62,.04),INK:(.7,.38,.65,.5),CREAM:(.02,.02,.07,0),'#FFFFFF':(0,0,0,0)}
FILES={'Fraunces':'Fraunces-Italic.ttf','Jakarta':'PlusJakartaSans.ttf','Outfit':'Outfit.ttf','DM':'DMSans.ttf','Cormorant':'CormorantGaramond-Italic.ttf'}
PAIRS=[('I','Fraunces','Jakarta',600,800),('II','Outfit','DM',700,500),('III','Cormorant','Jakarta',600,700)]
FONTS={}
def font(key,weight):
 if (key,weight) not in FONTS:
  f=TTFont(OUT/'fonts'/FILES[key]); axes={a.axisTag:a.defaultValue for a in f['fvar'].axes}; axes['wght']=weight
  if 'opsz' in axes:axes['opsz']=72 if key=='Fraunces' else 14
  FONTS[key,weight]=instantiateVariableFont(f,axes,inplace=True)
 return FONTS[key,weight]
def tw(text,key,size,weight):
 f=font(key,weight); cmap=f.getBestCmap(); return sum(f['hmtx'][cmap[ord(c)]][0] for c in text)/f['head'].unitsPerEm*size

def uri(path):
 p=Path(path); mime='image/jpeg' if p.suffix=='.jpg' else 'image/png'
 return 'data:'+mime+';base64,'+base64.b64encode(p.read_bytes()).decode()

class Scene:
 def __init__(self,w,h):self.w=w;self.h=h;self.items=[]
 def text(self,s,x,y,size=16,key='Jakarta',weight=500,color=INK):self.items.append(('text',s,x,y,size,key,weight,color))
 def rect(self,x,y,w,h,c,alpha=1):self.items.append(('rect',x,y,w,h,c,alpha))
 def image(self,name,x,y,w,h,logo=False):self.items.append(('image',name,x,y,w,h,logo))
 def rule(self,x,y,w):self.rect(x,y,w,.6,GOLD)

def backdrop(pair):
 roman,display,body,dw,bw=pair;s=Scene(960,600)
 s.image('field-clean-bg.jpg',0,0,960,600)
 # Continuous full-width atmospheric veil; never a hard-edged white text panel.
 s.items.append(('veil',))
 s.image('bnt-root-mark.png',58,40,161,103,True)
 s.text('BIOLOGICAL NUTRIENT',245,68,13,body,bw,G)
 s.text('TECHNOLOGIES',245,88,13,body,bw,G)
 s.text('BioNuTech.com',730,65,14,body,bw,G)
 s.rule(245,108,657)
 s.text('In a world where everyone else is the same,',60,188,21,display,dw,B)
 x=60;size=420/7.2
 for text,c in [('Be ',G),('differe',B),('NT.',G)]:
  s.text(text,x,264,size,display,dw,c);x+=tw(text,display,size,dw)
 s.text('Biological Plant Nutrition. Organic Acids. Reliable Results.',62,295,18,body,bw,G)
 s.rule(62,313,840)
 s.text('BioNuTech.com',62,338,15,body,bw,G)
 s.text('JeffGr@BioNuTech.com',347,338,14,body,500,INK)
 s.text('805-714-0173',731,338,14,body,500,INK)
 return s

def banner():
 s=Scene(330,800);s.rect(0,0,330,800,CREAM)
 s.image('bnt-root-mark.png',31,34,131,84,True)
 s.text('BIOLOGICAL NUTRIENT',31,144,12,'Jakarta',800,G);s.text('TECHNOLOGIES',31,161,12,'Jakarta',800,G)
 s.rule(31,181,268)
 s.text('In a world where everyone',31,212,12,'Fraunces',600,B);s.text('else is the same,',31,229,12,'Fraunces',600,B)
 x=31
 for t,c in [('Be ',G),('differe',B),('NT.',G)]:s.text(t,x,278,35,'Fraunces',600,c);x+=tw(t,'Fraunces',35,600)
 for num,title,sub,y in [('01','Biological Plant Nutrition','Plant nutrition for your growing program.',328),('02','Organic Acids Complex','Explore humic and fulvic acid options.',411),('03','Reliable Field Results','Discuss your crop and field priorities.',494)]:
  s.rule(31,y-16,268);s.text(num,31,y+6,11,'Jakarta',800,B);s.text(title,58,y+6,13,'Jakarta',800,G)
  s.text(sub,31,y+32,10,'DM',500,INK)
 s.items.append(('fieldcrop',))
 s.rect(0,647,330,153,G)
 s.image('qr-bionutech.png',31,676,67,67)
 s.text('BioNuTech.com',112,690,15,'Jakarta',800,'#FFFFFF')
 s.text('JeffGr@BioNuTech.com',112,712,10,'DM',500,'#FFFFFF')
 s.text('805-714-0173',112,731,12,'Jakarta',700,'#FFFFFF')
 return s

def svg_content(s):
 out=[]
 for it in s.items:
  if it[0]=='veil':
   out.append('<rect x="-2.5" y="-2.5" width="965" height="402.5" fill="url(#veil)"/>');continue
  if it[0]=='fieldcrop':
   out.append(f'<svg x="0" y="555" width="330" height="92" viewBox="0 0 330 92"><image href="{uri(ROOT/"assets"/"field-clean-bg.jpg")}" x="0" y="-114.25" width="330" height="206.25"/></svg>');continue
  if it[0]=='rect':
   _,x,y,w,h,c,a=it;out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{c}" opacity="{a}"/>')
  elif it[0]=='image':
   _,n,x,y,w,h,logo=it; clip='clip-path="url(#logoClip)"' if logo else ''
   if logo:out.append(f'<svg x="{x}" y="{y}" width="{w}" height="{h}" viewBox="0 0 580 370"><image href="{uri(ROOT/"assets"/n)}" width="580" height="370" {clip}/></svg>')
   else:out.append(f'<image href="{uri(ROOT/"assets"/n)}" x="{x}" y="{y}" width="{w}" height="{h}" preserveAspectRatio="none"/>')
  else:
   _,t,x,y,size,key,weight,c=it;out.append(f'<text x="{x}" y="{y}" font-family="{key}{weight}" font-size="{size}" fill="{c}" style="font-kerning:none">{html.escape(t)}</text>')
 return ''.join(out)
def make_svg(s,path,variants=None,bleed=False):
 # Static font instances embedded: SVG previews work offline and editable text is retained.
 definitions=[]
 scenes=variants or [('Artwork',s)]
 keys=set((i[5],i[6]) for _,sc in scenes for i in sc.items if i[0]=='text')
 for k,w in sorted(keys):
  buf=BytesIO();ff=font(k,w);family=f'{k}{w}'
  for nid in [1,4,6]:ff['name'].setName(family,nid,3,1,0x409)
  ff.save(OUT/'fonts'/f'{family}.ttf');ff.save(buf);data=base64.b64encode(buf.getvalue()).decode()
  definitions.append(f'@font-face{{font-family:"{k}{w}";src:url(data:font/ttf;base64,{data}) format("truetype");}}')
 b=2.5 if bleed else 0
 start=f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" width="{(s.w+2*b)/10}in" height="{(s.h+2*b)/10}in" viewBox="{-b} {-b} {s.w+2*b} {s.h+2*b}"><title>BioNuTech live editable vector source</title><defs><style>{"".join(definitions)}</style><linearGradient id="veil" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#F5F2E7" stop-opacity=".97"/><stop offset=".80" stop-color="#F5F2E7" stop-opacity=".90"/><stop offset="1" stop-color="#F5F2E7" stop-opacity="0"/></linearGradient><clipPath id="logoClip"><path d="M0 0H580V56H450V190H580V370H0Z"/></clipPath></defs>'
 if bleed and s.w==330:start+='<rect x="-2.5" y="-2.5" width="335" height="805" fill="#F5F2E7"/><rect x="-2.5" y="647" width="335" height="155.5" fill="#1B5E20"/>'
 if bleed and s.w!=330:start+=f'<image href="{uri(ROOT/"assets"/"field-clean-bg.jpg")}" x="{-b}" y="{-b}" width="{s.w+2*b}" height="{s.h+2*b}" preserveAspectRatio="none"/>'
 for idx,(label,sc) in enumerate(scenes):
  start+=f'<g id="{label}" inkscape:groupmode="layer" inkscape:label="{label}" style="display:{"inline" if idx==0 else "none"}">{svg_content(sc)}</g>'
 start+=f'<g id="Print-guides-NONPRINT" inkscape:groupmode="layer" inkscape:label="NONPRINT - Trim, 2.5in safe, 65 percent zone" style="display:none" fill="none" stroke="#CC00AA" stroke-width=".5"><rect x="0" y="0" width="{s.w}" height="{s.h}"/><rect x="25" y="25" width="{s.w-50}" height="{s.h-50}" stroke-dasharray="5 4"/><path d="M0 {s.h*.65}H{s.w}" stroke-dasharray="5 4"/></g></svg>'
 path.write_text(start)

class PDFPen(BasePen):
 def __init__(self,gs):super().__init__(gs);self.ops=[]
 def _moveTo(self,p):self.ops.append(f'{p[0]:.3f} {p[1]:.3f} m')
 def _lineTo(self,p):self.ops.append(f'{p[0]:.3f} {p[1]:.3f} l')
 def _curveToOne(self,a,b,c):self.ops.append(' '.join(f'{v:.3f}' for p in (a,b,c) for v in p)+' c')
 def _qCurveToOne(self,a,b):
  p=self._getCurrentPoint(); self._curveToOne((p[0]+2*(a[0]-p[0])/3,p[1]+2*(a[1]-p[1])/3),(b[0]+2*(a[0]-b[0])/3,b[1]+2*(a[1]-b[1])/3),b)
 def _closePath(self):self.ops.append('h')
 def _endPath(self):pass

PROFILE=Path('/System/Library/ColorSync/Profiles/Generic CMYK Profile.icc')
CMS=ImageCms.buildTransform(ImageCms.createProfile('sRGB'),ImageCms.getOpenProfile(str(PROFILE)),'RGB','CMYK')
def pdf(s,path):
 d=fitz.open();W=(s.w+5)*7.2;H=(s.h+5)*7.2;p=d.new_page(width=W,height=H)
 p.set_trimbox(fitz.Rect(18,18,W-18,H-18));p.set_bleedbox(p.mediabox)
 objs={};alphas={};ops=['q','7.2 0 0 -7.2 18 '+str(H-18)+' cm']
 def image_obj(name):
  if name in objs:return objs[name]
  im=Image.open(ROOT/'assets'/name);alpha=im.getchannel('A') if im.mode=='RGBA' else None
  cmyk=ImageCms.applyTransform(im.convert('RGB'),CMS);b=BytesIO();cmyk.save(b,format='TIFF',compression='raw')
  # Lossless CMYK samples, no RGB image objects.
  xo=d.get_new_xref();mask=''
  if alpha:
   ma=d.get_new_xref();d.update_object(ma,f'<< /Type /XObject /Subtype /Image /Width {im.width} /Height {im.height} /ColorSpace /DeviceGray /BitsPerComponent 8 >>');d.update_stream(ma,alpha.tobytes(),compress=True);mask=f'/SMask {ma} 0 R'
  d.update_object(xo,f'<< /Type /XObject /Subtype /Image /Width {im.width} /Height {im.height} /ColorSpace /DeviceCMYK /BitsPerComponent 8 {mask} >>');d.update_stream(xo,cmyk.tobytes(),compress=True)
  ident='Im'+str(len(objs));objs[name]=(ident,xo);return ident,xo
 def draw_image(name,x,y,w,h,logo=False):
  ident,_=image_obj(name);ops.append('q')
  if logo:
   sx=w/580;sy=h/370;ops.append(f'{sx} 0 0 {sy} {x} {y} cm 0 0 m 580 0 l 580 56 l 450 56 l 450 190 l 580 190 l 580 370 l 0 370 l h W n 580 0 0 -370 0 370 cm /{ident} Do Q')
  else:ops.append(f'{w} 0 0 {-h} {x} {y+h} cm /{ident} Do Q')
 draw_image('field-clean-bg.jpg',-2.5,-2.5,s.w+5,s.h+5)
 if s.w==330:
  ops.append(' '.join(map(str,CMYK[CREAM]))+' k -2.5 -2.5 335 805 re f')
  ops.append(' '.join(map(str,CMYK[G]))+' k -2.5 647 335 155.5 re f')
 for it in s.items:
  if it[0]=='fieldcrop':
   ops.append('q 0 555 330 92 re W n');draw_image('field-clean-bg.jpg',0,440.75,330,206.25);ops.append('Q');continue
  if it[0]=='veil':
   f1=d.get_new_xref();d.update_object(f1,'<< /FunctionType 2 /Domain [0 1] /C0 [.97] /C1 [.90] /N 1 >>')
   f2=d.get_new_xref();d.update_object(f2,'<< /FunctionType 2 /Domain [0 1] /C0 [.90] /C1 [0] /N 1 >>')
   fn=d.get_new_xref();d.update_object(fn,f'<< /FunctionType 3 /Domain [0 1] /Functions [{f1} 0 R {f2} 0 R] /Bounds [.8] /Encode [0 1 0 1] >>')
   sh=d.get_new_xref();d.update_object(sh,f'<< /ShadingType 2 /ColorSpace /DeviceGray /Coords [0 0 0 400] /Function {fn} 0 R /Extend [true true] >>')
   form=d.get_new_xref();d.update_object(form,f'<< /Type /XObject /Subtype /Form /BBox [-2.5 -2.5 962.5 400] /Group << /S /Transparency /CS /DeviceGray >> /Resources << /Shading << /Sh {sh} 0 R >> >> >>');d.update_stream(form,b'/Sh sh')
   alphas['Veil']=f'<< /Type /ExtGState /SMask << /S /Luminosity /G {form} 0 R /BC [0] >> >>'
   ops.append('q /Veil gs '+' '.join(map(str,CMYK[CREAM]))+' k -2.5 -2.5 965 402.5 re f Q');continue
  if it[0]=='image':draw_image(*it[1:]);continue
  if it[0]=='rect':
   _,x,y,w,h,c,a=it;an='A'+str(round(a*10000));alphas[an]=a;ops.append('q /'+an+' gs '+' '.join(map(str,CMYK[c]))+f' k {x} {y} {w} {h} re f Q');continue
  _,t,x,y,size,key,weight,c=it;f=font(key,weight);gs=f.getGlyphSet();cmap=f.getBestCmap();scale=size/f['head'].unitsPerEm
  ops.append('q '+' '.join(map(str,CMYK[c]))+f' k {scale} 0 0 {-scale} {x} {y} cm')
  for char in t:
   name=cmap[ord(char)];pen=PDFPen(gs);gs[name].draw(pen);ops.extend(pen.ops);ops.append('f');advance=f['hmtx'][name][0];ops.append(f'1 0 0 1 {advance} 0 cm')
  ops.append('Q')
 ops.append('Q');res=d.get_new_xref();d.update_object(res,'<< /XObject << '+' '.join(f'/{n} {xref} 0 R' for n,xref in objs.values())+' >> /ExtGState << '+' '.join((f'/{k} {a}' if isinstance(a,str) else f'/{k} << /Type /ExtGState /ca {a} /CA {a} >>') for k,a in alphas.items())+' >> >>');d.xref_set_key(p.xref,'Resources',f'{res} 0 R')
 content=d.get_new_xref();d.update_object(content,'<<>>');d.update_stream(content,'\n'.join(ops).encode(),compress=True);d.xref_set_key(p.xref,'Contents',f'{content} 0 R')
 icc=d.get_new_xref();d.update_object(icc,'<< /N 4 >>');d.update_stream(icc,PROFILE.read_bytes(),compress=True)
 oi=d.get_new_xref();d.update_object(oi,f'<< /Type /OutputIntent /S /GTS_PDFX /OutputConditionIdentifier (Generic CMYK - replace with printer profile) /DestOutputProfile {icc} 0 R >>');d.xref_set_key(d.pdf_catalog(),'OutputIntents',f'[{oi} 0 R]')
 d.set_metadata({'title':'BioNuTech - CMYK outlined production artwork','subject':'Printer approval required: low resolution source imagery; Generic CMYK profile. Not certified PDF/X.','creator':'BioNuTech export builder'})
 d.save(path,garbage=4,deflate=True);d.close()


def main():
 scenes=[(p[0],backdrop(p)) for p in PAIRS]
 for r,s in scenes:make_svg(s,OUT/f'Pairing-{r}.svg')
 make_svg(scenes[0][1],OUT/'BioNuTech_8x5_Editable_LiveText.svg',scenes,True)
 bs=banner();make_svg(bs,OUT/'BioNuTech_33x80_VerticalBanner_Editable.svg')
 make_svg(bs,OUT/'BioNuTech_33x80_VerticalBanner_WithBleed.svg',bleed=True)
 pdf(scenes[0][1],OUT/'BioNuTech_8x5_CMYK_PressReady_Outlined.pdf')
 pdf(bs,OUT/'BioNuTech_33x80_CMYK_Outlined.pdf')
 guide='''# BioNuTech typography and print handoff

I — Editorial Botanical Heritage: Fraunces Italic 600 display + Plus Jakarta Sans ExtraBold 800. Warm, distinctive, recommended master.
II — Modern Agronomic Science: Outfit Bold 700 + DM Sans Medium 500. Clearest broad-stroke distance option.
III — Executive Luxury Ag-Biotech: Cormorant Garamond Semibold Italic 600 + Plus Jakarta Sans Bold 700. Refined high contrast; test thin strokes on fabric.

All three full backdrop previews use actual embedded font instances, not substitutes. Fonts and OFL licenses are included. In the master SVG, enable exactly one named I/II/III layer. NONPRINT guide layer is hidden by default; never print it. Text remains live. Fonts use named embedded static instances for reliable previews; install supplied named static font instances (for example Fraunces600.ttf) or original families and reassign live text if an editor ignores SVG font embedding. PDFs contain glyph outlines, no font dependency. Logo and photography remain supplied raster assets.

Trim: backdrop 96 x 60 inches; Media/BleedBox 96.5 x 60.5 inches, TrimBox inset 0.25 inch. Banner trim 33 x 80 inches; bleed PDF 33.5 x 80.5 inches. One inch = 10 SVG units = 72 PDF points. Safe perimeter 2.5 inches inside trim. PDF files contain artwork only; specification is a separate sheet to prevent accidental extra-sheet printing.

All backdrop key copy ends at 33.8 inches from top, inside the upper 65% (39 inches). At a bottom mounting height of 30 inches above floor, lowest baseline is 56.2 inches above floor, above a 30-inch table. This is an installation assumption, not an unconditional guarantee for a floor-mounted backdrop. Banner contact dock is at 7-12 inches above floor and must stand beside the table, not behind it. Bottom 5 inches reserved for cassette, subject to stand vendor template.

Main backdrop slogan: 420 pt em size. Em height at 10 m subtends 50.9 arcminutes; actual x-height is smaller. Under-three-second recognition requires an actual aisle test; not a measured claim. Requested 2.1:1 to 11.4:1 AAA improvement is not measured. WCAG screen contrast is not a fabric print certification.

CMYK vector recipes: botanical green 82/35/88/28; earth brown 32/64/84/26; harvest gold 18/28/62/4. RGB SVG swatches are screen references; these are proposed ink recipes, not asserted colorimetric matches. PDF raster assets converted from sRGB using macOS Generic CMYK ICC, which is embedded as OutputIntent. Ask printer for device/substrate ICC and proof. PDF includes transparency; not a certified PDF/X file.

PRINT RELEASE LIMITATION: field source is 1920 x 1200, approximately 20 DPI at 96 x 60 inches (19.9 DPI including bleed). A real 150 DPI full-size image needs at least 14400 x 9000 pixels at trim. No artificial upsampling claim is made. Source contains cleanup artifacts near horizon. Replace with licensed original high-resolution retouched image before final print release. Logo source 580 x 370 is about 36 DPI at its 16.1-inch width; obtain original vector logo. Partial descriptor in supplied logo is clipped while the full descriptor is recreated as live text. Product/service support copy is proposed only; no unverified efficacy promises. QR is the supplied asset; scan-test the physical proof before production.

The filename PressReady is retained to match the requested manifest. Geometry, CMYK conversion and outlined typography are implemented; final press approval is conditional on source resolution, retouching, printer profile and hardware template.
'''
 (OUT/'Font_Pairing_and_Print_Guide.md').write_text(guide)
 spec=Scene(595/7.2,842/7.2);spec.rect(0,0,spec.w,spec.h,CREAM)
 lines=['BioNuTech / Production specification','96 x 60 in backdrop | 33 x 80 in banner','0.25 in bleed / 2.5 in safe margin','Outlined typography / CMYK image and vector objects','Embedded output intent: Generic CMYK','Green: 82 / 35 / 88 / 28','Brown: 32 / 64 / 84 / 26','Gold: 18 / 28 / 62 / 4','420 pt display / 10 m recognition: test required','Mount backdrop bottom 30 in above floor.','PRINT RELEASE HOLD: source photograph is ~20 DPI.','150 DPI target needs 14400 x 9000 px at trim.','Logo source is raster (~36 DPI); request vector.','Replace cleaned photo: visible horizon artifacts.','Confirm printer ICC, material and banner cassette.','Not certified PDF/X; transparency is retained.','Full details: Font_Pairing_and_Print_Guide.md']
 for i,line in enumerate(lines):spec.text(line,5,9+i*5.6,1.5 if i else 2.2,'Jakarta',800 if i==0 else 500,G)
 pdf(spec,OUT/'BioNuTech_CMYK_Specification.pdf')
 checks={}
 for name in ['BioNuTech_8x5_CMYK_PressReady_Outlined.pdf','BioNuTech_33x80_CMYK_Outlined.pdf']:
  d=fitz.open(OUT/name);p=d[0];checks[name]={'media_inches':[round(p.rect.width/72,3),round(p.rect.height/72,3)],'trim_inches':[round(p.trimbox.width/72,3),round(p.trimbox.height/72,3)],'font_count':len(p.get_fonts()),'extracted_text_chars':len(p.get_text()),'image_colorspaces':sorted(set(x[5] for x in p.get_images()))};assert not p.get_fonts() and not p.get_text();p.get_pixmap(matrix=fitz.Matrix(.18,.18)).save(OUT/(name.removesuffix('.pdf')+'_Proof.png'))
 checks['photo_native_dpi']=20;checks['release_status']='HOLD: higher-resolution photo and vector logo, printer profile/proof required';(OUT/'Preflight_Report.json').write_text(json.dumps(checks,indent=2))
 files=[p for p in OUT.rglob('*') if p.is_file() and p.suffix in ('.svg','.pdf','.md','.json','.ttf','.txt')]
 with zipfile.ZipFile(OUT/'BioNuTech_Expo_Booth_Master_Pack.zip','w',zipfile.ZIP_DEFLATED) as z:
  for p in files:z.write(p,p.relative_to(OUT))
  z.write(__file__,'build_exports.py')
  for p in (ROOT/'assets').iterdir():z.write(p,'assets/'+p.name)
 print(json.dumps(checks,indent=2));print('Archive rebuilt:',OUT/'BioNuTech_Expo_Booth_Master_Pack.zip')
if __name__=='__main__':main()
