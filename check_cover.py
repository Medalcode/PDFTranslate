import fitz

doc = fitz.open(r'D:\Github\PDFTranslate\pruebas\Hadoop - the Definitive Guide.pdf')

with open('cover_sizes.txt', 'w', encoding='utf-8') as f:
    for page_num in range(4):
        f.write(f'--- Page {page_num} ---\n')
        page = doc[page_num]
        for b in page.get_text('dict')['blocks']:
            if b['type'] == 0:
                max_size = 0
                for l in b['lines']:
                    for s in l['spans']:
                        if s['size'] > max_size: 
                            max_size = s['size']
                text = ''.join(' '.join(s['text'] for s in l['spans']) for l in b['lines']).strip()
                f.write(f'size={max_size:.1f} text={text[:60]}\n')
