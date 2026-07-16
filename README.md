# NetEase Album Wallpaper / 网易云专辑封面墙

粘贴一个网易云音乐**公开歌单**链接或完整分享文案，自动下载去重后的专辑封面，并生成按颜色自然过渡的画廊式壁纸。

<img width="1920" height="1200" alt="专辑封面墙生成效果预览" src="https://github.com/user-attachments/assets/e5a2ed7f-bc12-4136-9c98-81134d4771e9" />

```text
分享歌单: 我喜欢的音乐 https://163cn.tv/xxxxxx (@网易云音乐)
                              ↓
解析歌单 → 按 album.id 去重 → 下载封面 → Lab 色彩聚类 → 圆角画廊壁纸
```

## 特性

- 支持 `163cn.tv` 分享短链、完整歌单链接、纯数字歌单 ID 和整段分享文案
- 只读取公开歌单，不需要网易云账号或 Cookie
- 按网易云返回的 `album.id` 去重，同一张专辑只下载一次
- 在 CIELAB 感知色彩空间中提取主色并优化相邻封面的色差
- 自动选择接近画布比例的网格，尽量减少补位封面
- 深色背景、居中留白、方形圆角卡片和细间距
- 默认输出 3840×2400 PNG，同时生成布局 CSV
- 支持保留下载的原始封面，方便二次创作

## 安装

需要 Python 3.10 或更高版本。

```bash
git clone https://github.com/flowerzm/netease-album-wallpaper.git
cd netease-album-wallpaper
python3 -m pip install -e .
```

## 使用

最简单的方式：

```bash
netease-album-wallpaper "https://163cn.tv/xxxxxx"
```

也可以直接粘贴分享文案：

```bash
netease-album-wallpaper "分享歌单: 我喜欢的音乐 https://163cn.tv/xxxxxx (@网易云音乐)"
```

输出到指定位置：

```bash
netease-album-wallpaper "https://music.163.com/playlist?id=123456789" \
  --output my-wallpaper.png
```

保留下载的专辑封面：

```bash
netease-album-wallpaper "https://163cn.tv/xxxxxx" \
  --covers-dir ./covers \
  --output wallpaper.png
```

自定义画布和样式：

```bash
netease-album-wallpaper "https://163cn.tv/xxxxxx" \
  --width 3840 \
  --height 2400 \
  --gap 10 \
  --radius 12 \
  --background "#090c13" \
  --output wallpaper.png
```

查看所有参数：

```bash
netease-album-wallpaper --help
```

## 输出

- `wallpaper.png`：生成的壁纸
- `wallpaper.layout.csv`：每张封面在网格中的位置和 Lab 色彩信息
- `wallpaper.manifest.json`：歌单、专辑和下载结果摘要
- `--covers-dir` 指定的目录：可选，保存原始封面

## 工作原理

1. 跟随网易云分享短链的 HTTP 重定向，提取歌单 ID。
2. 调用网易云公开页面使用的歌单与歌曲详情接口。
3. 以 `album.id` 作为主键去除重复专辑。
4. 对每张封面进行调色板量化，并转换到 CIELAB 色彩空间。
5. 先按色相与明度生成初始二维布局，再用局部交换降低相邻格子的 Lab 色差。
6. 按自动计算的网格绘制圆角封面、细间距、阴影和深色背景。

## 致谢与参考

感谢以下开源作者和项目提供的实现思路：

| 作者（GitHub 主页） | 项目 | 本项目参考的内容 |
| --- | --- | --- |
| [@SoujiOkita98](https://github.com/SoujiOkita98) | [playlist-roast-skill](https://github.com/SoujiOkita98/playlist-roast-skill) | 网易云公开歌单信息提取与歌曲详情请求思路 |
| [@Linsxyx](https://github.com/Linsxyx) | [KugouMusic.NET](https://github.com/Linsxyx/KugouMusic.NET) | 网易云分享短链重定向及歌单链接解析思路 |
| [@stephanlensky](https://github.com/stephanlensky) | [spy-collage](https://github.com/stephanlensky/spy-collage) | 按色彩组织图片并生成封面拼贴墙的思路 |

本项目针对网易云歌单、专辑去重、封面下载和单命令壁纸生成工作流进行了独立的 Python 实现；仓库中未直接包含上述项目的源文件。

## 限制与说明

- 仅支持公开歌单；私密歌单需要登录，本项目不会读取 Cookie。
- 网易云接口或短链规则变化后可能需要更新。
- 少量已下架、地区受限或缺少封面的歌曲可能被跳过。
- 请控制使用频率，不要对网易云服务造成压力。
- MIT 许可证仅适用于本仓库代码。专辑封面版权归原权利人所有，不随本项目授权。
- 本工具仅用于个人音乐收藏整理、学习和研究，请遵守网易云音乐服务条款及所在地法律。

## 开发

```bash
python3 -m pip install -e .
python3 -m unittest discover -s tests -v
```

欢迎提交 Issue 和 Pull Request。
