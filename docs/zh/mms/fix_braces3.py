import re
path = r"D:\opensource\arch-quality\docs\zh\mms\openfoam_rhopimple_mms.py"
with open(path, encoding="utf-8") as f:
    src = f.read()

# The source code has literal "\n" (backslash + n), not actual newlines
# Replace \n); }}\n with \n); }\n (remove extra close brace)
src = src.replace('\\n); }}\\n', '\\n); }\\n')

with open(path, "w", encoding="utf-8") as f:
    f.write(src)
print("Fixed")
