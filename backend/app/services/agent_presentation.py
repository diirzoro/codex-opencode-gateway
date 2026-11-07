"""Read-only assistant presentation; never mutate native conversation history."""
import re


def public_assistant_text(value):
    """Hide explicit think sections, preserving literal markers inside Markdown code."""
    text=str(value or '')
    protected=[]
    fence=None;start=0;offset=0
    for line in text.splitlines(keepends=True):
        match=re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$',line.rstrip('\r\n'))
        if match:
            marker=match[1]
            if fence is None:fence=marker;start=offset
            elif marker[0]==fence[0] and len(marker)>=len(fence) and not match[2].strip():
                protected.append((start,offset+len(line)));fence=None
        inline=None
        for run in re.finditer(r'`+',line):
            if inline is None:inline=(offset+run.start(),len(run[0]))
            elif len(run[0])==inline[1]:
                protected.append((inline[0],offset+run.end()));inline=None
        offset+=len(line)
    if fence is not None:protected.append((start,len(text)))
    protected.sort()
    visible=[];position=0;depth=0;index=0
    for match in re.finditer(r'<\s*(/?)\s*think\s*>',text,re.I):
        while index<len(protected) and protected[index][1]<=match.start():index+=1
        if index<len(protected) and protected[index][0]<=match.start()<protected[index][1]:continue
        if depth==0:visible.append(text[position:match.start()])
        if not match[1]:depth+=1
        elif depth:depth-=1
        else:visible=[]  # Some runtimes omit the opening marker.
        position=match.end()
    if depth==0:visible.append(text[position:])
    return ''.join(visible).strip()


def reply_instructions(data,base):
    language=getattr(data,'response_language',None)
    if language is None:language='ar' if re.search(r'[\u0600-\u06ff]',data.text) else 'en'
    preference='Arabic' if language=='ar' else 'English'
    return base+'\nConversation language preference: '+preference+'. Use this language consistently for user-facing progress, questions and final reports unless the user explicitly requests another language. Keep code, commands, filenames, original output and quotations unchanged; explain foreign-language errors in the conversation language. Never include private deliberation or think markers.\nWhen asked to show the project or changes, direct the customer to the View changes card in this conversation. Do not claim the preview opened before the customer clicks it, and do not launch a persistent app through a shell as a substitute for isolated Preview.'


def preview_actions(workspace,session_id,message_id,prompt,activity,completed):
    if not completed or not message_id:return []
    changed=any(file.get('operation') in {'created','changed','moved','deleted'}
                for row in activity if row.get('status')=='completed' for file in row.get('files',[]))
    requested=bool(re.search(r'\bpreview\b|\b(?:show|view|open)\b.{0,60}\b(?:changes|project|app|result)\b|معاين|(?:اعرض|أظهر|اظهر|وريني|افتح).{0,60}(?:التغييرات|النتيجة|المشروع)',prompt,re.I))
    if not changed and not requested:return []
    return [{'kind':'preview','workspace_id':str(workspace.id),'project_id':str(workspace.project_id),
             'session_id':str(session_id),'message_id':str(message_id)}]
