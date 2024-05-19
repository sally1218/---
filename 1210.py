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
        await message.channel.send(f"你選擇的報告主題是：{selected_topic}。正在生成前言和實際應用案例，請稍後......")
        
        try:
            summary_response = openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": f"生成關於'{selected_topic}'的前言"}],
            )
            summary = summary_response.choices[0].message.content
            await message.channel.send(f"前言：\n{summary}")
            responses['summary'] = summary

            applications_response  = openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": f"生成關於'{selected_topic}'的實際應用案例"}],
            )
            applications = applications_response.choices[0].message.content
            await message.channel.send(f"實際應用案例：\n{applications}")
            responses['applications'] = applications

            await message.channel.send("你要進行存檔嗎？請回覆‘是’或‘否’。")
            responses['save_request'] = True  # 標記為需要等待存檔確認
            message_log.append(message.content)  # 更新日誌
        except OpenAIError as e:
            await message.channel.send(f"OpenAI 連接錯誤: {e}")

    elif responses.get('save_request') and message.content == '是':
        # 使用者要存檔
        path = "D:/sally_school"  # 設置默認保存路徑
        response_text = responses['summary']
        applications = responses['applications']
        report_topic = responses['report_topic']
        image_url = responses['image_url']
        image_data = requests.get(image_url).content
        image = Image.open(BytesIO(image_data))
        temp_image_path = f"{path}temp_image.png"
        image.save(temp_image_path)
        members_str = "組員: 蘇德恩、王品蓉、陳培昕"
        advisor_str = "指導老師: 鄞宗賢" 
        generate_pdf(report_topic, response_text, applications, temp_image_path, members_str, advisor_str, path)
        await message.channel.send("檔案已成功儲存!")
        await message.channel.send(file=discord.File(f"{path}response.pdf"))
        responses['save_request'] = False  # 重置保存請求狀態

# 生成 PDF 的函數
def generate_pdf(direction, summary, applications, image_path, members_str, advisor_str, path):
    # 使用正則表達式分割内容，确保每個點都在新的一行
    summary_lines = re.split(r'(?=\d+\.)', summary.strip())  # 這會根據數字點（如1. 2.）分割前言文本
    applications_lines = re.split(r'(?=\d+\.)', applications.strip())  # 這會根據數字點（如1. 2.）分割實際應用案例文本
    # 設定行高
    line_height = 25
    # 計算文本總高度
    summary_height = len(summary_lines) * line_height
    applications_height = len(applications_lines) * line_height
    # 計算頁面總高度
    page_height = summary_height + applications_height + 1200

    
    # 創建 PDF 並設定頁面大小
    c = canvas.Canvas(f"{path}response.pdf", pagesize=(A4[0], page_height))
    # 第一頁：標題和作者
    c.setFont("ChineseFont", 24)
    c.drawCentredString(A4[0] // 2, A4[1] - 50, direction)
    c.setFont("ChineseFont", 12)
    c.drawCentredString(A4[0] // 2, A4[1] - 250, members_str)
    c.drawCentredString(A4[0] // 2, A4[1] - 270, advisor_str)
    c.showPage()
    # 第二頁：内容
    c.setFont("ChineseFont", 12)
    c.drawString(80, page_height - 80, "前言：")
    # 設定寫入文本的起始位置
    text_x = 100
    text_y = page_height - 80 - line_height
    # 遍歷每行文本並寫入 PDF
    for line in summary_lines:
        c.drawString(text_x, text_y, line)
        text_y -= line_height
    
    # 寫入 PDF 實際應用案例標題
    c.drawString(80, page_height - 80 - summary_height - 80, "實際應用案例：")

    # 設定寫入實際應用案例文本的起始位置
    text_x = 100
    text_y = page_height - 80 - summary_height - 80 - line_height
    # 遍歷每行實際應用案例文本並寫入 PDF
    for line in applications_lines:
        c.drawString(text_x, text_y, line)
        text_y -= line_height

    # 調整圖像大小並在第二頁插入圖像
    image = Image.open(image_path)
    image_width, image_height = image.size
    max_image_width = A4[0] - 300
    max_image_height = A4[1] - 300
    if image_width > max_image_width or image_height > max_image_height:
        ratio = min(max_image_width / image_width, max_image_height / image_height)
        image = image.resize((int(image_width * ratio), int(image_height * ratio)))
    c.drawImage(image_path, 100, 100, width=image.size[0], height=image.size[1])

    # 保存 PDF 文件
    c.save()
    os.remove(image_path)

client.run("discord_bot_key")