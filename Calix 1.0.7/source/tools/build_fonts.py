"""Derive static faces from the supplied font; preserve all original glyphs."""
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

root=Path(__file__).resolve().parents[1]/'asset/style'
source=TTFont(root/'PretendardVariable.ttf',recalcTimestamp=False)
for weight,style in ((400,'Regular'),(500,'Medium'),(600,'SemiBold'),(700,'Bold')):
    target=root/f'CalixSans-{style}.ttf'
    font=instantiateVariableFont(source,{'wght':weight},inplace=False,optimize=True)
    for record in font['name'].names:
        values={1:'Calix Sans',2:style,3:f'CalixSans-{weight}-1.0',4:f'Calix Sans {style}',6:f'CalixSans-{style}',16:'Calix Sans',17:style,25:'CalixSans'}
        if record.nameID in values:record.string=values[record.nameID].encode(record.getEncoding())
    font['OS/2'].usWeightClass=weight
    font['OS/2'].fsSelection=(font['OS/2'].fsSelection&~((1<<5)|(1<<6)))|((1<<5) if weight==700 else (1<<6) if weight==400 else 0)
    font['head'].macStyle=(font['head'].macStyle&~1)|(1 if weight==700 else 0)
    assert 'fvar' not in font and len(font.getGlyphOrder())==len(source.getGlyphOrder())
    font.recalcTimestamp=False;font.save(target);print(target.name,target.stat().st_size,flush=True)
