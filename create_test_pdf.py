import fitz

doc = fitz.open()
page = doc.new_page()
page.insert_text((50, 50), "PDFTranslate Test Document", fontsize=20, fontname="helv")
page.insert_text((50, 100), "This is a simple test document to verify the translation pipeline.", fontsize=12)
page.insert_text((50, 150), "It should translate this sentence to Spanish.", fontsize=12)

# Insert a code block to verify code is NOT translated
code_text = "def hello_world():\n    print('Hello World')\n    return True"
page.insert_text((50, 200), code_text, fontsize=10, fontname="courier")

page.insert_text((50, 300), "Images and layout should be preserved perfectly.", fontsize=12)

doc.save("test.pdf")
doc.close()
print("test.pdf created!")
