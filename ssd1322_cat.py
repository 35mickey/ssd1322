from PIL import Image, ImageDraw, ImageFont
import time
import spidev
import gpiod

class SSD1322:
    def __init__(self, width=256, height=64):
        self.width = width
        self.height = height

        # 使用Pillow创建一个图像对象，模式为1（单色图）
        self.image = Image.new('1', (self.width, self.height))
        self.draw = ImageDraw.Draw(self.image)

        # 初始化显示
        time.sleep(0.005)
        self.init_display()

    def init_display(self):
        self.write_cmd(0xFD)  # Set Command Lock (MCU protection status)
        self.write_data(0x12)  # 0x12 = Unlock Basic Commands; 0x16 = lock

        self.write_cmd(0xA4)  # Set Display Mode = OFF

        self.write_cmd(0xB3)  # Set Front Clock Divider / Oscillator Frequency
        self.write_data(0x91)  # 0x91 = 80FPS; 0xD0 = default / 1100b

        self.write_cmd(0xCA)  # Set MUX Ratio
        self.write_data(0x3F)  # 0x3F = 63d = 64MUX (1/64 duty cycle)

        self.write_cmd(0xA2)  # Set Display Offset
        self.write_data(0x00)  # 0x00 = (default)

        self.write_cmd(0xA1)  # Set Display Start Line
        self.write_data(0x00)  # 0x00 = register 00h

        self.write_cmd(0xA0)  # Set Re-map and Dual COM Line mode
        self.write_data(0x14)  # 0x14 = Default except Enable Nibble Re-map, Scan from COM[N-1] to COM0, where N is the Multiplex ratio
        self.write_data(0x11)  # 0x11 = Enable Dual COM mode (MUX <= 63)

        self.write_cmd(0xB5)  # Set GPIO
        self.write_data(0x00)  # 0x00 = {GPIO0, GPIO1 = HiZ (Input Disabled)}

        self.write_cmd(0xAB)  # Function Selection
        self.write_data(0x01)  # 0x01 = Enable internal VDD regulator (default)

        self.write_cmd(0xB4)  # Display Enhancement A
        self.write_data(0xA0)  # 0xA0 = Enable external VSL; 0xA2 = internal VSL
        self.write_data(0xB5)  # 0xB5 = Normal (default); 0xFD = 11111101b = Enhanced low GS display quality

        self.write_cmd(0xC1)  # Set Contrast Current
        self.write_data(0x7F)  # 0x7F = (default)

        self.write_cmd(0xC7)  # Master Contrast Current Control
        self.write_data(0x0F)  # 0x0F = (default)

        self.write_cmd(0xB8)  # Select Custom Gray Scale table (GS0 = 0)
        for value in [0x00, 0x02, 0x08, 0x0D, 0x14, 0x1A, 0x20, 0x28, 0x30, 0x38, 0x40, 0x48, 0x50, 0x60, 0x70, 0x00]:
            self.write_data(value)

        self.write_cmd(0xB1)  # Set Phase Length
        self.write_data(0xE2)  # 0xE2 = Phase 1 period (reset phase length) = 5 DCLKs,
                               # Phase 2 period (first pre-charge phase length) = 14 DCLKs

        self.write_cmd(0xD1)  # Display Enhancement B
        self.write_data(0xA2)  # 0xA2 = Normal (default); 0x82 = reserved
        self.write_data(0x20)  # 0x20 = as-is

        self.write_cmd(0xBB)  # Set Pre-charge voltage
        self.write_data(0x1F)  # 0x17 = default; 0x1F = 0.60*Vcc (spec example)

        self.write_cmd(0xB6)  # Set Second Precharge Period
        self.write_data(0x08)  # 0x08 = 8 dclks (default)

        self.write_cmd(0xBE)  # Set VCOMH
        self.write_data(0x07)  # 0x04 = 0.80*Vcc (default); 0x07 = 0.86*Vcc (spec example)

        self.write_cmd(0xA6)  # Set Display Mode = Normal Display
        self.write_cmd(0xA9)  # Exit Partial Display
        self.write_cmd(0xAF)  # Set Sleep mode OFF (Display ON)

        self.fill(0)
        self.show()

    def poweroff(self):
        self.write_cmd(0xAB)
        self.write_data(0x00)  # Disable internal VDD regulator, to save power
        self.write_cmd(0xAE)

    def poweron(self):
        self.write_cmd(0xAB)
        self.write_data(0x01)  # Enable internal VDD regulator
        self.write_cmd(0xAF)

    def contrast(self, contrast):
        self.write_cmd(0x81)
        self.write_data(contrast)

    def rotate(self, rotate):
        self.write_cmd(0xA0)
        self.write_data(0x06 if rotate else 0x14)
        self.write_data(0x11)

    def invert(self, invert):
        self.write_cmd(0xA4 | (invert & 1) << 1 | (invert & 1))  # 0xA4=Normal, 0xA7=Inverted

    # 将每个位扩展4倍，因为SSD1322是4位颜色深度
    def expand_bits(self, data):
        result = bytearray()

        for byte in data:
            expanded_byte = 0
            # 扩展每个字节的每一位
            for i in range(8):
                bit = (byte >> (7 - i)) & 0x01  # 获取字节的第 i 位
                expanded_byte += ((bit * 0x0F) << (4 * (7 - i)))

            # 将扩展后的结果拆成 4 个字节，每个字节保持在 8 位以内
            for i in range(4):
                result.append((expanded_byte >> (8 * (3 - i))) & 0xFF)

        return result

    def show(self):
        # Convert the Pillow image into raw data
        # image_data = self.image.convert('1')  # Convert to 1-bit black and white image
        byte_data = self.expand_bits(self.image.tobytes())
        # self.image.save("./aaa.jpg")

        offset = (480 - self.width) // 2
        col_start = offset // 4
        col_end = col_start + self.width // 4 - 1

        self.write_cmd(0x15)
        self.write_data(col_start)
        self.write_data(col_end)

        self.write_cmd(0x75)
        self.write_data(0)
        self.write_data(self.height - 1)

        self.write_cmd(0x5C)

        # self.Column_Address(0,0+self.width//4-1)
        # self.Row_Address(0,0+self.height-1)

        self.write_data(byte_data)

    def fill(self, col):
        self.draw.rectangle((0, 0, self.width - 1, self.height - 1), fill=col)

    def pixel(self, x, y, col):
        self.draw.point((x, y), fill=col)

    def line(self, x1, y1, x2, y2, col):
        self.draw.line((x1, y1, x2, y2), fill=col)

    def text(self, string, x, y, col=255):
        font = ImageFont.load_default()  # 使用默认字体
        self.draw.text((x, y), string, fill=col, font=font)

    # # 设置显示的列起始和终止地址
    # def Column_Address(self, a, b):
        # self.write_cmd(0x15)  # Set Column Address
        # self.write_data(0x1c + a)
        # self.write_data(0x1c + b)

    # # 设置显示的行起始和终止地址
    # def Row_Address(self, a, b):
        # self.write_cmd(0x75)  # Set Row Address
        # self.write_data(a)
        # self.write_data(b)
        # self.write_cmd(0x5C)  # Write RAM

    # # OLED 填充指定区域
    # def OLED_Fill(self, xstr, ystr, xend, yend, color):
        # xstr //= 4
        # xend //= 4
        # self.Column_Address(xstr, xend - 1)
        # self.Row_Address(ystr, yend - 1)
        # for x in range(xstr, xend):
            # for y in range(ystr, yend):
                # self.write_data(color)
                # self.write_data(color)

    def write_cmd(self, cmd):
        raise NotImplementedError

    def write_data(self, data):
        raise NotImplementedError

class SSD1322_SPI(SSD1322):
    def __init__(self, width, height, spi_dev, dc_line, res_line):
        self.spi = spi_dev
        self.dc = dc_line
        self.res = res_line

        self.res.set_value(1)
        time.sleep(0.01)
        self.res.set_value(0)
        time.sleep(0.01)
        self.res.set_value(1)

        super().__init__(width, height)
        time.sleep(0.01)

    def write_cmd( self, aCommand ) :
        '''Write given command to the device.'''
        self.dc.set_value(0)
        self.spi.xfer2(bytearray([aCommand]))

    def write_data(self, aData):
        '''Write given data to the device. This may be either a single int or a bytearray of values.'''
        self.dc.set_value(1)

        # 如果数据是bytes或bytearray，将数据分块发送
        if isinstance(aData, (bytes, bytearray)):
            # 每块最大 4096 字节
            max_chunk_size = 4096
            for i in range(0, len(aData), max_chunk_size):
                chunk = aData[i:i + max_chunk_size]
                self.spi.xfer2(chunk)
        else:
            # 发送单个字节
            self.spi.xfer2([aData])

# 主程序
if __name__ == "__main__":

    # GPIO 引脚设置
    RES_PIN = 1  # 低电平复位引脚 A1
    DC_PIN = 0   # 数据-1/命令-0选择引脚 A0

    # 获取 GPIO 通道
    chip = gpiod.Chip('gpiochip1')  # GPIO1 设备
    res_line = chip.get_line(RES_PIN)  # 获取复位引脚
    dc_line = chip.get_line(DC_PIN)   # 获取 DC 引脚

    # 配置 GPIO 引脚为输出模式
    res_line.request(consumer="py_oled", type=gpiod.LINE_REQ_DIR_OUT)
    dc_line.request(consumer="py_oled", type=gpiod.LINE_REQ_DIR_OUT)

    # SPI 配置
    spi_dev = spidev.SpiDev()
    spi_dev.open(3, 1)  # 打开 /dev/spidev3.1
    spi_dev.mode = 0  # 设置为模式 0
    spi_dev.bits_per_word = 8  # 设置每个数据字为 8 位
    spi_dev.max_speed_hz = 8000000  # 设置 SPI 时钟频率为 8 MHz

    # OLED 控制命令
    SSD1322_WIDTH = 256
    SSD1322_HEIGHT = 64

    disp=SSD1322_SPI(SSD1322_WIDTH,SSD1322_HEIGHT,spi_dev,dc_line,res_line)
    disp.text("Hello SBB!",0,0,1)
    disp.text("GoodBye SBB!",160,50,1)
    disp.line(0,63,255,0,1)
    disp.show()
