"""Derive explicit oblique faces under the existing Calix Sans OFL name.

Qt's Windows GDI fallback enumerates installed fonts for an absent italic
face. Providing the face also keeps Korean rich text in the bundled family.
"""
from pathlib import Path
from math import tan,radians
from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen

root=Path(__file__).resolve().parents[1]/'asset/style'
for weight,source,style in ((400,'Regular','Italic'),(700,'Bold','BoldItalic')):
    font=TTFont(root/f'CalixSans-{source}.ttf',recalcTimestamp=False)
    if 'STAT' in font:del font['STAT']
    glyphset=font.getGlyphSet();glyphs={}
    for name in font.getGlyphOrder():
        record=DecomposingRecordingPen(glyphset);glyphset[name].draw(record)
        pen=TTGlyphPen(None);record.replay(TransformPen(pen,(1,0,tan(radians(12)),1,0,0)))
        glyphs[name]=pen.glyph()
    font['glyf'].glyphs=glyphs
    for name,glyph in glyphs.items():
        glyph.recalcBounds(font['glyf'])
        advance,_=font['hmtx'].metrics[name]
        font['hmtx'].metrics[name]=(advance,getattr(glyph,'xMin',0))
    font['hhea'].caretSlopeRise=1000;font['hhea'].caretSlopeRun=round(tan(radians(12))*1000)
    subfamily='Italic' if weight==400 else 'Bold Italic'
    values={1:'Calix Sans',2:subfamily,3:f'CalixSans-{weight}-Italic-1.0',4:f'Calix Sans {subfamily}',6:f'CalixSans-{style}',16:'Calix Sans',17:subfamily,25:'CalixSans'}
    for record in font['name'].names:
        if record.nameID in values:record.string=values[record.nameID].encode(record.getEncoding())
    font['OS/2'].fsSelection=(font['OS/2'].fsSelection&~(1<<6))|1
    font['head'].macStyle|=2;font['post'].italicAngle=-12
    for table in ('fpgm','prep','cvt ','hdmx','LTSH'):
        if table in font:del font[table]
    target=root/f'CalixSans-{style}.ttf';font.save(target)
    print(target.name,target.stat().st_size,flush=True)
