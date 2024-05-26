import discord
import os
from openai import OpenAI, OpenAIError  
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas
from PIL import Image
from io import BytesIO 
import io
import requests
import textwrap
import re

# OpenAI API 金鑰
openai_client = OpenAI(api_key="api_key")

# client是跟discord連接，intents是要求機器人的權限
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# 創建一個列表來存儲訊息
message_log = []

responses = {}

# 載入字體
pdfmetrics.registerFont(TTFont('ChineseFont', 'D:/sally_school/專題四/jf-openhuninn-2.0.ttf'))

# 調用event函式庫
@client.event
# 當機器人完成啟動
async def on_ready():
    print(f"目前登入身份 --> {client.user}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith("我要製作一份報告"):
        await message.channel.send("請問您想要做什麼樣的報告？請提供主題。")
        message_log.append(message.content)  # 儲存以便日後處理

    elif len(message_log) == 1 and not message.content.startswith('存檔'):
        report_topic = message.content
        supplemental_text = "請針對該主題，提出四個跟該主題有關的報告標題。"
        question_with_supplement = f"{report_topic}\n\n{supplemental_text}"
        
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4", 
                messages=[{"role": "user", "content": question_with_supplement}],
            )
            response_text = response.choices[0].message.content
            report_titles = response_text.split("\n")
            await message.channel.send(f"選擇的報告主題為：\n" + "\n".join(report_titles))

            response = openai_client.images.generate(
                model="dall-e-3",
                prompt=report_topic,
                size="1024x1024",
                quality="standard",
                n=1,
            )
            image_url = response.data[0].url
            responses['image_url'] = image_url
            responses['report_titles'] = report_titles
            responses['report_topic'] = report_topic
            message_log.append(message.content)  # 更新日誌
        except OpenAIError as e:
            await message.channel.send(f"OpenAI 連接錯誤: {e}")

    elif len(message_log) == 2:
        selected_index = int(message.content.strip()) - 1
        selected_topic = responses['report_titles'][selected_index]
        await message.channel.send(f"你選擇的報告主題是：{selected_topic}。正在生成前言，請稍後......")
        
        try:
            summary_response = openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": f"生成關於'{selected_topic}'的前言"}],
            )
            summary = summary_response.choices[0].message.content
            await message.channel.send(f"生成的前言：\n{summary}")
            responses['summary'] = summary

            await message.channel.send("請提供一段簡短的內容介紹，我們將幫你修正語句使其更正式完整。")
            message_log.append(message.content)  # 更新日誌
        except OpenAIError as e:
            await message.channel.send(f"OpenAI 連接錯誤: {e}")
    
    elif len(message_log) == 3:
        intro_text = message.content
        try:
            intro_response = openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": intro_text}],
            )
            revised_intro = intro_response.choices[0].message.content
            await message.channel.send(f"修正後的內容介紹：\n{revised_intro}")
            responses['revised_intro'] = revised_intro
            
            # 提供實例和新聞連結
            examples_response = openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": f"提供三個關於'{responses['report_topic']}'的應用實例和一個新聞連結。"}],
            )
            examples_and_link = examples_response.choices[0].message.content
            await message.channel.send(f"相關實例和新聞連結：\n{examples_and_link}")
            responses['examples_and_link'] = examples_and_link

            await message.channel.send("你要進行存檔嗎？請回覆‘是’或‘否’。")
            message_log.append(message.content)  # 更新日誌
            responses['save_request'] = True
        except OpenAIError as e:
            await message.channel.send(f"OpenAI 連接錯誤: {e}")

    elif responses.get('save_request') and message.content == '是':
        # 使用者要存檔
        path = "D:/sally_school"  # 設置默認保存路徑
        image_url = responses['image_url']
        image_data = requests.get(image_url).content
        image = Image.open(BytesIO(image_data))
        temp_image_path = f"{path}temp_image.png"
        image.save(temp_image_path)
        response_text = responses['summary']
        members_str = "組員: 蘇德恩、王品蓉、陳培昕"
        advisor_str = "指導老師: 鄞宗賢" 
        generate_pdf(responses['report_topic'], responses['summary'], responses['revised_intro'], responses['examples_and_link'], temp_image_path,members_str,advisor_str, path)
        await message.channel.send("檔案已成功儲存!")
        await message.channel.send(file=discord.File(f"{path}response.pdf"))
        responses['save_request'] = False  # 重置保存請求狀態

# 生成 PDF 的函數
def generate_pdf(direction, summary, intro,examples_and_link, image_path, members_str, advisor_str, path):
    c = canvas.Canvas(f"{path}response.pdf", pagesize=A4)
    c.setFont("ChineseFont", 12)
    margin = 72
    page_width, page_height = A4
    text_width = page_width - 2 * margin
    text_y = page_height - margin

    # 寫入報告標題
    c.setFont("ChineseFont", 24)
    c.drawCentredString(A4[0] / 2, A4[1] - 100, direction)
    text_y -= 30
    c.setFont("ChineseFont", 12)
    c.drawCentredString(A4[0] / 2, A4[1] - 550, members_str)
    c.drawCentredString(A4[0] / 2, A4[1] - 570, advisor_str)
    c.showPage()
    # 第二頁：内容
    c.setFont("ChineseFont", 15)
    c.drawString(margin,text_y, "前言：")
    summary_lines = textwrap.wrap(summary, width=38)  # 自動換行
    for line in summary_lines:
        text_y -= 15
        c.setFont("ChineseFont", 12)
        c.drawString(margin, text_y, line)

     # 新增空行
    text_y -= 20
    
    # 寫入內容介紹
    c.setFont("ChineseFont", 15)
    c.drawString(margin, text_y, "內容介紹：")
    intro_lines = textwrap.wrap(intro, width=38)  # 自動換行
    for line in intro_lines:
        text_y -= 15
        c.setFont("ChineseFont", 12)
        c.drawString(margin, text_y, line)

    # 新增空行
    text_y -= 20

    # 寫入實例和新聞連結
    c.setFont("ChineseFont", 15)
    c.drawString(margin, text_y, "相關實例和新聞連結：")
    text_y -= 15
    for line in textwrap.wrap(examples_and_link, width=38):
        c.setFont("ChineseFont", 12)
        c.drawString(margin, text_y, line)
        text_y -= 15

    # 插入圖片
    img = Image.open(image_path)
    img_width, img_height = img.size
    scale = min(text_width / img_width, (text_y - margin) / img_height)
    img = img.resize((int(img_width * scale), int(img_height * scale)))
    c.drawInlineImage(img, margin, text_y - img_height * scale, width=img_width * scale, height=img_height * scale)

    # 保存 PDF 文件
    c.save()
    os.remove(image_path)

client.run("discord_bot_key")