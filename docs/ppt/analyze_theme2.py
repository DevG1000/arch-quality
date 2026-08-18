import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import zipfile
import re

with zipfile.ZipFile(r'D:\opensource\arch-quality\docs\ppt\SKILL开发指南PPT.pptx', 'r') as z:
    # Full theme XML
    with z.open('ppt/theme/theme1.xml') as f:
        xml = f.read().decode('utf-8')
    
    # Extract color scheme
    m = re.search(r'<a:clrScheme name="([^"]+)">(.*?)</a:clrScheme>', xml, re.DOTALL)
    if m:
        print(f"Color scheme: {m.group(1)}")
        colors = re.findall(r'<a:(\w+)>.*?srgbClr val="([0-9A-Fa-f]+)".*?</a:\1>', m.group(2))
        for name, val in colors:
            print(f"  {name}: #{val}")
    
    print()
    
    # Font scheme in detail
    m = re.search(r'<a:fontScheme name="([^"]+)">(.*?)</a:fontScheme>', xml, re.DOTALL)
    if m:
        print(f"Font scheme: {m.group(1)}")
        major = re.search(r'<a:majorFont>(.*?)</a:majorFont>', m.group(2), re.DOTALL)
        minor = re.search(r'<a:minorFont>(.*?)</a:minorFont>', m.group(2), re.DOTALL)
        if major:
            print("  Major (headings):")
            for tf in re.findall(r'<a:(\w+) typeface="([^"]+)"', major.group(1)):
                print(f"    {tf[0]}: {tf[1]}")
        if minor:
            print("  Minor (body):")
            for tf in re.findall(r'<a:(\w+) typeface="([^"]+)"', minor.group(1)):
                print(f"    {tf[0]}: {tf[1]}")
    
    print()
    
    # Now check all slides' rPr elements for direct font specifications
    for i in range(22):
        slide_path = f'ppt/slides/slide{i+1}.xml'
        try:
            with z.open(slide_path) as f:
                slide_xml = f.read().decode('utf-8')
        except:
            continue
        
        # Find all rPr with font info
        font_infos = set()
        for m in re.finditer(r'<a:rPr[^>]*>(.*?)</a:rPr>', slide_xml, re.DOTALL):
            rpr = m.group(0)
            sz = re.search(r'sz="(\d+)"', rpr)
            sz_val = int(sz.group(1)) / 100 if sz else None
            b = ' b="1"' in rpr or ' b="true"' in rpr.lower()
            latin = re.search(r'<a:latin typeface="([^"]+)"', rpr)
            ea = re.search(r'<a:ea typeface="([^"]+)"', rpr)
            color = re.search(r'<a:solidFill>.*?srgbClr val="([0-9A-Fa-f]+)"', rpr)
            
            font_info = f"sz={sz_val} bold={b} lat={(latin.group(1) if latin else 'N/A')} ea={(ea.group(1) if ea else 'N/A')} color={('#'+color.group(1) if color else 'N/A')}"
            font_infos.add(font_info)
        
        if font_infos:
            for fi in sorted(font_infos):
                print(f"  Slide {i+1}: {fi}")
