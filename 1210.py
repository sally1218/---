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
import random
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
                model="gpt-3.5-turbo", 
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
                model="gpt-3.5-turbo",
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
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": intro_text}],
            )
            revised_intro = intro_response.choices[0].message.content
            await message.channel.send(f"修正後的內容介紹：\n{revised_intro}")
            responses['revised_intro'] = revised_intro
            
            # 提供實例和新聞連結
            examples_response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": f"提供三個關於'{responses['report_topic']}'的應用實例。"}],
            )
            examples = examples_response.choices[0].message.content
            await message.channel.send(f"相關應用實例：\n{examples}")
            responses['examples'] = examples

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
        generate_pdf(responses['report_topic'], responses['summary'], responses['revised_intro'], responses['examples'], temp_image_path, path)
        await message.channel.send("檔案已成功儲存!")
        await message.channel.send(file=discord.File(f"{path}response.pdf"))
        responses['save_request'] = False  # 重置保存請求狀態

# 生成 PDF 的函數
def generate_pdf(direction, summary, intro, examples, image_path, path):
    c = canvas.Canvas(f"{path}response.pdf", pagesize=A4)
    c.setFont("ChineseFont", 12)
    margin = 72
    page_width, page_height = A4
    text_y = page_height - margin

    # 隨機選擇背景圖片
    bg_number = random.randint(1, 4)  # 生成1至4之間的隨機數
    cover_image_path = f'D:/sally_school/專題四/bg{bg_number}.webp'  # 構建圖片路徑
    cover_image = Image.open(cover_image_path)
    cover_image_w, cover_image_h = cover_image.size
    cover_scale = min(page_width / cover_image_w, page_height / cover_image_h)
    cover_image = cover_image.resize((int(cover_image_w * cover_scale), int(cover_image_h * cover_scale)))
    c.drawInlineImage(cover_image, 0, 0, width=page_width, height=page_height)

    # 創建封面
    c.setFont("ChineseFont", 18)
    c.drawCentredString(page_width / 2, page_height - 300, f"報告標題：{direction}")
    c.setFont("ChineseFont", 14)
    c.drawCentredString(page_width / 2, page_height - 350, "組員名稱: 蘇德恩, 王品蓉, 陳培昕")
    c.drawCentredString(page_width / 2, page_height - 400, "指導老師: 鄞老師")
    c.showPage()  # 新增一頁來開始內文

    # 寫入前言
    c.setFont("ChineseFont", 16)  # 放大標題字體
    c.drawString(margin, text_y, "前言：")
    text_y -= 30
    c.setFont("ChineseFont", 12)
    summary_lines = textwrap.wrap(summary, width=35)
    for line in summary_lines:
        text_y -= 15
        c.drawString(margin, text_y, line)

    text_y -= 30  # 增加更大的間距

    # 寫入內容介紹
    c.setFont("ChineseFont", 16)
    c.drawString(margin, text_y, "內容介紹：")
    text_y -= 30
    c.setFont("ChineseFont", 12)
    intro_lines = textwrap.wrap(intro, width=35)
    for line in intro_lines:
        text_y -= 15
        c.drawString(margin, text_y, line)
    text_y -= 30
    
    # 處理並顯示圖片
    img = Image.open(image_path)
    img_width, img_height = img.size
    scale = min((page_width - 2 * margin) / img_width, (page_height - text_y - 200) / img_height, 0.25)  # 最大縮放比例為0.3
    img = img.resize((int(img_width * scale), int(img_height * scale)))
    c.drawInlineImage(img, margin, text_y - img.height - 20, width=img.width, height=img.height)
    
    text_y -= img.height + 50  # 調整 text_y 位置
    
    # 檢查是否有足夠空間顯示相關實例
    if text_y < margin:
        c.showPage()  # 新增一頁
        text_y = page_height - margin
    
    # 處理實例
    c.setFont("ChineseFont", 16)
    c.drawString(margin, text_y, "相關實例：")
    text_y -= 30
    c.setFont("ChineseFont", 12)
    example_lines = textwrap.wrap(examples, width=35)
    for line in example_lines:  # 確保顯示所有行
        if text_y < margin:
            c.showPage()  # 新增一頁
            text_y = page_height - margin
        text_y -= 15
        c.drawString(margin, text_y, line)

    c.save()
    os.remove(image_path)

client.run("discord_bot_key")