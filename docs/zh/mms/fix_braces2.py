path = r"D:\opensource\arch-quality\docs\zh\mms\openfoam_rhopimple_mms.py"
with open(path, encoding="utf-8") as f:
    src = f.read()

# Fix: \n); }}\n -> \n); }\n  (remove extra brace in non-f-string)
src = src.replace('\n); }}\n', '\n); }\n')

with open(path, "w", encoding="utf-8") as f:
    f.write(src)
print("Fixed braces")
