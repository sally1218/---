import discord
import os
from openai import OpenAI, OpenAIError  # 匯入 OpenAI 模組
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas
from PIL import Image
from io import BytesIO 
import io
import requests
import textwrap

# OpenAI API 金鑰
openai_client = OpenAI(api_key="my_api_key")

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
    # 排除機器人本身的訊息，避免無限循環
    if message.author == client.user:
        return

    # 新訊息包含"我要製作一份報告"，要求提供報告主題
    if message.content.startswith("我要製作一份報告"):
        await message.channel.send("請問您想要做什麼樣的報告？請提供主題。")
        # 將接收到的訊息添加到訊息日誌
        message_log.append(message.content)
    # 如果訊息日誌中已經有主題信息
    elif len(message_log) == 1:
        # 從訊息日誌中獲取報告主題
        report_topic = message.content
        supplemental_text = "請針對該主題，提出四個跟該主題有關的報告標題。"
        question_with_supplement = f"{report_topic}\n\n{supplemental_text}"
        try:
            # 調用 OpenAI GPT-4 模型
            response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo", 
                messages=[{"role": "user", "content": question_with_supplement}], 
            )
            # 從response中提取文本內容
            response_text = response.choices[0].message.content
            response = openai_client.images.generate(
                model="dall-e-3",
                prompt=report_topic,
                size="1024x1024",
                quality="standard",
                n=1,
            )
            image_url = response.data[0].url
            responses['image_url'] = image_url
            responses['save_request'] = True
            responses['response_text'] = response_text
            responses['report_topic'] = report_topic            
            await message.channel.send("報告已生成，請提供存檔的路徑（絕對路徑），例如：存檔 C:/Users/User/Documents/")
        except OpenAIError as e:
            # 處理可能的 OpenAI 連線錯誤
            await message.channel.send(f"OpenAI 連線錯誤: {e}")
        # 清空訊息日誌
        message_log.clear()

    if responses.get('save_request'):
        if message.content.startswith('存檔') and ' ' in message.content:
            path = message.content.split(' ')[1]
            response_text = responses['response_text']
            report_topic = responses['report_topic']
            image_url = responses['image_url']
            image_data = requests.get(image_url).content
            image = Image.open(BytesIO(image_data))
            temp_image_path = f"{path}temp_image.png"
            image.save(temp_image_path)
            members_str = "組員: 蘇德恩、王品蓉、陳培昕" 
            advisor_str = "指導老師: 鄞宗賢"
            generate_pdf(report_topic, response_text, temp_image_path,members_str, advisor_str,path)
            responses['save_request'] = False
            await message.channel.send("報告已成功儲存至指定路徑。")
            await message.channel.send(file=discord.File(f"{path}response.pdf"))
            return  
        else:
            pass
    else:
        pass

# 生成 PDF 的函數
def generate_pdf(direction, content, image_path, members_str,advisor_str, path):
    # 處理文本換行
    lines = textwrap.wrap(content, width=30)
    # 設定行高
    line_height = 25
    # 計算文本總高度
    text_height = len(lines) * line_height
    # 計算頁面總高度
    page_height = text_height + 800
    # 創建 PDF 並設定頁面大小
    c = canvas.Canvas(f"{path}response.pdf", pagesize=(A4[0], A4[1]))

    # 第一頁：標題和作者
    c.setFont("ChineseFont", 24)
    c.drawCentredString(A4[0] // 2, A4[1] - 50, direction)
    c.setFont("ChineseFont", 12)
    c.drawString(100, 100, members_str)
    c.drawRightString(A4[0] - 100, 100, advisor_str)
    c.showPage()

    # 第二頁：内容
    c.setFont("ChineseFont", 12)
    c.drawString(100, page_height - 100, "摘要：")
    y = A4[1] - 80  
    for line in lines:
        if y < 100:  
            c.showPage()
            y = A4[1] - 80
        c.drawString(100, y, line)
        y -= line_height

    # 調整圖像大小並在第二頁插入圖像
    image = Image.open(image_path)
    image_width, image_height = image.size
    max_image_width = A4[0] - 200
    max_image_height = A4[1] - 200
    if image_width > max_image_width or image_height > max_image_height:
        ratio = min(max_image_width / image_width, max_image_height / image_height)
        image = image.resize((int(image_width * ratio), int(image_height * ratio)))
    c.drawImage(image_path, 100, 100, width=image.size[0], height=image.size[1])
  
    # 保存 PDF 文件
    c.save()
    os.remove(image_path)

client.run("discord bot key")