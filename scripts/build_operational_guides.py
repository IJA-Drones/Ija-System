"""Gera PDFs individuais por módulo, sem acessar serviços.

Uso: python scripts/build_operational_guides.py
Dependências: reportlab, Pillow e pypdf. Ver TRAINING_FONT_DIR em
training_pdf_style.py. Conteúdo e fontes: docs/treinamentos/guias-operacionais.json.
"""
import json
from pathlib import Path
import shutil

from PIL import Image
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics

from training_pdf_style import (ACCENT, CONTENT, HEIGHT, INK, LINE, MARGIN,
                                MUTED, SOFT, TEAL_SOFT, WIDTH, chrome, heading,
                                panel, paragraph, register_fonts, text)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs/treinamentos/guias-operacionais.json'
CAPTURES = SOURCE.parent / 'capturas-guias'
OUTPUT = ROOT / 'output/pdf'
LIBRARY = ROOT / 'app/resources/treinamentos/manuais/biblioteca'
REVIEW = ROOT / 'docs/treinamentos/validacao-guias-operacionais.json'


def check_space(y, guide, page):
    if y < 68:
        raise ValueError(f'{guide["id"]}, página {page}: conteúdo abaixo do rodapé ({y:.1f}).')


def flow(canvas_, labels, top):
    gap = 10
    width = (CONTENT - gap*2)/3
    height = 64
    for n, label in enumerate(labels):
        x = MARGIN+n*(width+gap)
        canvas_.setFillColor(SOFT)
        canvas_.roundRect(x, top-height, width, height, 9, fill=1, stroke=0)
        text(canvas_, f'{n+1:02d}', x+12, top-10, width-24, 9, 13, True, ACCENT)
        text(canvas_, label, x+12, top-29, width-24, 10, 14, True)
    return top-height


def draw_guide(guide):
    filename = guide['id']+'.pdf'
    target = OUTPUT / filename
    pdf = canvas.Canvas(str(target), pagesize=(WIDTH, HEIGHT), invariant=1)
    pdf.setTitle(guide['title']+' | Guia de uso | IJA System')
    pdf.setAuthor('Oceano Azul')
    pdf.setSubject('Guia operacional revisado em 17/11/2026. Capturas com dados fictícios.')
    for page in range(1,4):
        chrome(pdf, page, 3)
        key = f'p{page}'
        pdf.bookmarkPage(key)
        pdf.addOutlineEntry(('Visão geral','Passo a passo','Conferência e dúvidas')[page-1],key)
        if page==1:
            y=heading(pdf,'Guia de uso',guide['title'],guide['subtitle'])
            y=panel(pdf,'Para quem é este guia',guide['audience'],MARGIN,y,background=TEAL_SOFT)-13
            y=text(pdf,guide['menu'],MARGIN,y,size=9,leading=13,color=MUTED)-13
            y=flow(pdf,guide['flow'],y)-15
            image_path=CAPTURES/(guide['screenshot']+'.png')
            if not image_path.is_file():
                raise FileNotFoundError(f'Captura real não disponível: {image_path}')
            with Image.open(image_path) as im:
                iw,ih=im.size
            h=min(CONTENT*ih/iw,y-100)
            w=h*iw/ih
            x=MARGIN+(CONTENT-w)/2
            pdf.setStrokeColor(LINE)
            pdf.rect(x-1,y-h-1,w+2,h+2,fill=0,stroke=1)
            pdf.drawImage(str(image_path),x,y-h,w,h,preserveAspectRatio=True)
            y-=h+9
            y=text(pdf,'Tela real em ambiente local de demonstração, com dados fictícios. As opções dependem do perfil e dos módulos habilitados.',MARGIN,y,size=7.7,leading=11,color=MUTED)-9
            first='Passo a passo: página 2'
            separator='    |    '
            last='Conferência e dúvidas: página 3'
            y=text(pdf,first+separator+last,MARGIN,y,size=8,leading=12,bold=True,color=ACCENT)
            first_width=pdfmetrics.stringWidth(first,'Training-Bold',8)
            next_x=MARGIN+pdfmetrics.stringWidth(first+separator,'Training-Bold',8)
            pdf.linkRect('', 'p2', (MARGIN,y-1,MARGIN+first_width,y+13),relative=0,thickness=0)
            pdf.linkRect('', 'p3', (next_x,y-1,next_x+pdfmetrics.stringWidth(last,'Training-Bold',8),y+13),relative=0,thickness=0)
        elif page==2:
            y=heading(pdf,'Na prática','Passo a passo')
            before=' '.join(guide['before'])
            y=text(pdf,before,MARGIN,y,size=9.2,leading=13.2,color=MUTED)-14
            for n,(title,body) in enumerate(guide['steps'],1):
                _,bh=paragraph(body,CONTENT-45,10,14.7)
                height=bh+34
                pdf.setFillColor(SOFT if n%2 else TEAL_SOFT)
                pdf.roundRect(MARGIN,y-height,CONTENT,height,8,fill=1,stroke=0)
                text(pdf,f'{n:02d}',MARGIN+10,y-9,26,9,13,True,ACCENT)
                yy=text(pdf,title,MARGIN+35,y-8,CONTENT-45,10.8,15,True)
                text(pdf,body,MARGIN+35,yy-4,CONTENT-45,10,14.7)
                y-=height+7
            check_space(y,guide,page)
        else:
            y=heading(pdf,'Após usar a funcionalidade','Confira o resultado')
            y=text(pdf,'Antes de considerar a etapa concluída',MARGIN,y,size=12,leading=17,bold=True)-12
            for n,check in enumerate(guide['checks'],1):
                pdf.setStrokeColor(ACCENT)
                pdf.roundRect(MARGIN,y-11,10,10,2,fill=0,stroke=1)
                y=text(pdf,check,MARGIN+20,y,CONTENT-20,10,15)-10
            y-=7
            y=text(pdf,'Campos e referências',MARGIN,y,size=12,leading=17,bold=True)-10
            for label,body in guide['fields']:
                y=text(pdf,label,MARGIN,y,145,9.2,14,True,color=ACCENT)
                _,bh=paragraph(body,CONTENT-158,9.2,14)
                text(pdf,body,MARGIN+158,y+14,CONTENT-158,9.2,14)
                y-=max(0,bh-14)+12
                pdf.setStrokeColor(LINE);pdf.line(MARGIN,y+5,WIDTH-MARGIN,y+5)
            y-=8
            y=text(pdf,'Se algo não aparecer como esperado',MARGIN,y,size=12,leading=17,bold=True)-12
            for title,body in guide['faq']:
                y=panel(pdf,title,body,MARGIN,y)-9
            y-=3
            y=text(pdf,'Acesso: '+guide['menu'],MARGIN,y,size=8.5,leading=13,color=MUTED)-8
            y=text(pdf,'Dúvidas: consulte os demais guias da Central de Treinamentos ou o suporte da sua equipe. Contato geral: suporte@ijadrones.com.br.',MARGIN,y,size=8.2,leading=12,color=MUTED)
        check_space(y,guide,page)
        pdf.showPage()
    pdf.save()
    shutil.copy2(target,LIBRARY/filename)
    return target


def validate(guides):
    results=[]
    for g in guides:
        name=g['id']+'.pdf'
        path=OUTPUT/name
        reader=PdfReader(path)
        assert len(reader.pages)==3,(name,len(reader.pages))
        assert len(reader.outline)==3,name
        content='\n'.join(p.extract_text() or '' for p in reader.pages)
        assert g['title'] in content.replace('\n',' '),name
        assert 'suporte@ijadrones.com.br' in content,name
        assert 'joao.pedro' not in content.lower(),name
        assert path.read_bytes()==(LIBRARY/name).read_bytes(),name
        for source in g['sources']:
            assert (ROOT/source).is_file(),source
        results.append({'id':g['id'],'title':g['title'],'pages':3,'sources':g['sources']})
    REVIEW.write_text(json.dumps({'revision':'2026-11-17','guides':results,'total_pages':sum(g['pages'] for g in results),'note':'Validação estrutural. A revisão visual é registrada no inventário.'},ensure_ascii=False,indent=2)+'\n')
    return sum(g['pages'] for g in results)


def main():
    register_fonts()
    guides=json.loads(SOURCE.read_text())['guides']
    assert len({g['id'] for g in guides})==len(guides)
    OUTPUT.mkdir(parents=True,exist_ok=True);LIBRARY.mkdir(parents=True,exist_ok=True)
    for guide in guides:
        result=draw_guide(guide)
        print(result.name,flush=True)
    pages=validate(guides)
    print(f'{len(guides)} PDFs individuais; {pages} páginas ao todo; cópias da Central conferidas.')


if __name__=='__main__':
    main()
