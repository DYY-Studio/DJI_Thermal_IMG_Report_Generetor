import json

def convert_raw_lut_to_json(input_file, output_file):
    # dji_ircm 输出的格式为 256个色阶，每个色阶重复 25 次像素 (RGB)
    with open(input_file, 'rb') as f:
        data = f.read()
    
    lut_colors = []
    # 只需提取 256 个独特的颜色值
    for i in range(256):
        # 取得每一组（色阶）的第一个像素
        offset = i * 25 * 3
        r = data[offset]
        g = data[offset + 1]
        b = data[offset + 2]
        lut_colors.append([r, g, b])
    
    # 导出为 JSON 供前端读取
    with open(output_file, 'w') as f:
        json.dump(lut_colors, f)
    print(f"转换完成: {output_file}")

for i in range(0, 10):
    convert_raw_lut_to_json(r'D:\Work\Batch\DJI_Thermal_IMG_Reporter\lut\lut{}.raw'.format(i), r'D:\Work\Batch\DJI_Thermal_IMG_Reporter\lut\lut{}.json'.format(i))