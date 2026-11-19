# -*- coding: utf-8 -*-
"""云旅 App 设计图生成：用例图 / 活动图×2 / 类图 / 架构图。
运行：python tools/make_diagrams.py  -> 输出 diagrams/*.png
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Polygon, FancyArrowPatch, Ellipse, Circle, Rectangle

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

OUT = 'd:/flutter项目/云旅flutter+ai/diagrams/'
BLUE = '#2f6fb0'
GRAY = '#555555'
BORDER = '#333333'
LIGHT = '#eef4fb'
LIGHT2 = '#f6f8fb'


def new_ax(w, h, x1, y1, title, ts=15):
    fig = plt.figure(figsize=(w, h))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, x1)
    ax.set_ylim(0, y1)
    ax.axis('off')
    fig.suptitle(title, fontsize=ts, fontweight='bold', y=0.98)
    return fig, ax


def arrow(ax, p1, p2, color=BORDER, ls='-', lw=1.2, rad=0.0):
    a = FancyArrowPatch(p1, p2, arrowstyle='-|>', mutation_scale=13, linewidth=lw,
                        linestyle=ls, color=color, connectionstyle=f'arc3,rad={rad}', zorder=2)
    ax.add_patch(a)


def line(ax, p1, p2, color=BORDER, ls='-', lw=1.2):
    ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=color, linestyle=ls, linewidth=lw, zorder=2)


def actor(ax, x, y, label, fs=10):
    ax.add_patch(Circle((x, y + 1.15), 0.22, facecolor='white', edgecolor=BORDER, linewidth=1.4, zorder=3))
    line(ax, (x, y + 0.93), (x, y + 0.35), lw=1.4)
    line(ax, (x - 0.28, y + 0.7), (x + 0.28, y + 0.7), lw=1.4)
    line(ax, (x, y + 0.35), (x - 0.22, y - 0.1), lw=1.4)
    line(ax, (x, y + 0.35), (x + 0.22, y - 0.1), lw=1.4)
    ax.text(x, y - 0.55, label, fontsize=fs, ha='center', fontweight='bold')


# ==================== 1. 用例图 ====================
def draw_use_case():
    fig, ax = new_ax(12, 8, 12, 8, '图1  云旅 App 用例图')
    ax.add_patch(Rectangle((2.3, 0.9), 8.0, 6.3, fill=False, edgecolor=BORDER, linewidth=1.6, zorder=1))
    ax.text(2.5, 7.0, '云旅 App（旅游规划助手）', fontsize=12, fontweight='bold', color=BLUE, va='center')

    actor(ax, 0.9, 4.0, '游客', 11)
    actor(ax, 11.1, 4.0, 'DeepSeek AI', 10)

    cases = [
        (4.4, 6.0, '浏览城市'), (4.4, 4.6, '录入需求'), (4.4, 3.2, '生成行程方案'),
        (7.2, 6.0, '浏览方案与行程'), (7.2, 4.6, '编辑行程'), (7.2, 3.2, '收藏与历史'),
        (9.8, 6.0, '查询交通与门票'), (9.8, 4.6, '导出行程单'), (9.8, 3.2, '设置偏好'),
    ]
    for cx, cy, label in cases:
        ax.add_patch(Ellipse((cx, cy), 2.5, 1.05, facecolor='white', edgecolor=BORDER, linewidth=1.3, zorder=3))
        ax.text(cx, cy, label, fontsize=9.5, ha='center', va='center', zorder=4)

    for cx, cy, _ in cases:
        arrow(ax, (1.7, 4.0), (cx - 1.25, cy))
    arrow(ax, (10.35, 4.0), (5.65, 3.2), ls='--', color=GRAY)
    ax.text(8.6, 3.35, '«include»\nAI 增强', fontsize=7.5, color=GRAY, ha='center')

    fig.savefig(OUT + 'uml_use_case.png', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)


# ==================== 活动图辅助 ====================
def act_node(ax, x, y, text, w=4.2, h=1.0, fs=9.5):
    ax.add_patch(FancyBboxPatch((x - w/2, y - h/2), w, h, boxstyle='round,pad=0.05,rounding_size=0.25',
                                facecolor=LIGHT, edgecolor=BORDER, linewidth=1.3, zorder=3))
    ax.text(x, y, text, fontsize=fs, ha='center', va='center', zorder=4)


def dec(ax, x, y, text, r=1.1, fs=8.0):
    ax.add_patch(Polygon([(x, y + r), (x + r, y), (x, y - r), (x - r, y)],
                         closed=True, facecolor='white', edgecolor=BORDER, linewidth=1.3, zorder=3))
    ax.text(x, y, text, fontsize=fs, ha='center', va='center', zorder=4)


def start(ax, x, y):
    ax.add_patch(Circle((x, y), 0.22, facecolor=BORDER, edgecolor=BORDER, zorder=3))


def end(ax, x, y):
    ax.add_patch(Circle((x, y), 0.32, facecolor='white', edgecolor=BORDER, linewidth=1.6, zorder=3))
    ax.add_patch(Circle((x, y), 0.16, facecolor=BORDER, edgecolor=BORDER, zorder=4))


def merge(ax, x, y):
    ax.plot([x - 0.7, x + 0.7], [y, y], color=BORDER, linewidth=1.6, zorder=3)


# ==================== 2. 活动图1：生成行程方案 ====================
def draw_activity_generate():
    fig, ax = new_ax(9, 11, 10, 15.5, '图2  活动图：生成行程方案流程')
    start(ax, 5, 14.5)
    act_node(ax, 5, 13.2, '录入需求\n(出发/目的/天数/预算/偏好)')
    act_node(ax, 5, 11.9, '准备本地城市数据\n(景点/酒店/美食)')
    dec(ax, 5, 10.0, 'DeepSeek\n可用?')

    act_node(ax, 2.2, 8.2, '本地规则引擎生成\n多风格方案并评分', w=3.4)
    act_node(ax, 8.0, 8.2, '调用 DeepSeek\n(数据注入)', w=3.4)
    dec(ax, 8.0, 6.2, '调用\n成功?', r=0.9)
    act_node(ax, 8.0, 4.5, 'AI 生成智能行程', w=3.2)
    act_node(ax, 4.3, 4.5, '回退本地规则引擎', w=3.2)

    merge(ax, 5, 3.0)
    act_node(ax, 5, 1.8, '展示方案列表')
    end(ax, 5, 0.5)

    # 主线
    arrow(ax, (5, 14.28), (5, 13.7))
    arrow(ax, (5, 12.7), (5, 12.4))
    arrow(ax, (5, 11.4), (5, 11.1))
    # 决策分支（否/是）
    arrow(ax, (3.9, 10.0), (2.2, 8.7))
    arrow(ax, (6.1, 10.0), (8.0, 8.7))
    ax.text(3.1, 9.9, '否', fontsize=9, color=GRAY)
    ax.text(6.9, 9.9, '是', fontsize=9, color=GRAY)
    # 左分支 -> 汇合
    arrow(ax, (2.2, 7.7), (2.2, 3.0))
    line(ax, (2.2, 3.0), (4.3, 3.0))
    # 右分支：调用 DeepSeek -> 决策 -> 成功/失败
    arrow(ax, (8.0, 7.7), (8.0, 7.1))
    arrow(ax, (8.0, 5.3), (8.0, 5.0))
    arrow(ax, (7.1, 6.2), (5.5, 5.0))
    ax.text(8.15, 5.15, '是', fontsize=8, color=GRAY)
    ax.text(6.4, 6.0, '否', fontsize=8, color=GRAY)
    # 右分支成功 -> 汇合
    arrow(ax, (8.0, 4.0), (8.0, 3.0))
    line(ax, (8.0, 3.0), (5.7, 3.0))
    # 回退 -> 汇合
    arrow(ax, (4.3, 4.0), (4.3, 3.0))
    # 汇合后
    arrow(ax, (5, 3.0), (5, 2.3))
    arrow(ax, (5, 1.3), (5, 0.82))

    fig.savefig(OUT + 'uml_activity_generate.png', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)


# ==================== 3. 活动图2：编辑并导出行程 ====================
def draw_activity_edit():
    fig, ax = new_ax(9, 10, 10, 14.5, '图3  活动图：编辑并导出行程流程')
    start(ax, 5, 13.8)
    act_node(ax, 5, 12.5, '选择方案')
    act_node(ax, 5, 11.2, '查看每日行程')
    act_node(ax, 5, 9.9, '增删景点 / 拖拽排序')
    act_node(ax, 5, 8.6, '预算实时统计')
    dec(ax, 5, 7.1, '保存到\n本地?')

    act_node(ax, 2.4, 5.8, '写入 SQLite', w=3.4)
    dec(ax, 5, 4.4, '导出\n行程单?')
    act_node(ax, 8.0, 4.4, '选择格式\n(txt/json)', w=3.4)
    act_node(ax, 8.0, 3.0, '写入文件', w=3.4)
    end(ax, 5, 1.5)

    # 主线
    arrow(ax, (5, 13.58), (5, 13.0))
    arrow(ax, (5, 12.0), (5, 11.7))
    arrow(ax, (5, 10.7), (5, 10.4))
    arrow(ax, (5, 9.4), (5, 9.1))
    arrow(ax, (5, 8.1), (5, 8.2))
    # 保存决策
    arrow(ax, (3.9, 7.1), (2.4, 6.3))
    arrow(ax, (5, 6.0), (5, 5.5))
    ax.text(3.0, 6.9, '是', fontsize=8, color=GRAY)
    ax.text(4.55, 5.75, '否', fontsize=8, color=GRAY)
    # 写入 SQLite 汇合到导出决策
    arrow(ax, (2.4, 5.3), (2.4, 4.4))
    line(ax, (2.4, 4.4), (3.9, 4.4))
    # 导出决策
    arrow(ax, (6.1, 4.4), (6.3, 4.4))
    arrow(ax, (5, 3.3), (5, 1.82))
    ax.text(6.2, 4.6, '是', fontsize=8, color=GRAY)
    ax.text(4.6, 2.5, '否', fontsize=8, color=GRAY)
    # 选择格式 -> 写入文件
    arrow(ax, (8.0, 3.9), (8.0, 3.5))
    # 写入文件 -> 结束
    arrow(ax, (8.0, 2.5), (8.0, 1.82))
    line(ax, (8.0, 1.82), (5.32, 1.82))

    fig.savefig(OUT + 'uml_activity_edit.png', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)


# ==================== 4. 类图 ====================
def class_box(ax, x, y, name, stereotype, attrs, methods, w=3.0):
    h = 0.9 + 0.34 * len(attrs) + 0.34 * len(methods) + 0.5
    top = y + h / 2
    ax.add_patch(FancyBboxPatch((x - w/2, top - 0.8), w, 0.8, boxstyle='square,pad=0.01',
                                facecolor=BLUE, edgecolor=BORDER, linewidth=1.3, zorder=3))
    ax.text(x, top - 0.4, name, ha='center', va='center', fontsize=9.5, fontweight='bold', color='white', zorder=4)
    ax.text(x, top - 0.63, stereotype, ha='center', va='center', fontsize=6.2, color='#d0e6ff', zorder=4)
    ax.add_patch(FancyBboxPatch((x - w/2, y - h/2), w, h - 0.8, boxstyle='square,pad=0.01',
                                facecolor='white', edgecolor=BORDER, linewidth=1.3, zorder=3))
    yy = top - 0.8 - 0.28
    for a in attrs:
        ax.text(x - w/2 + 0.12, yy, a, ha='left', va='center', fontsize=6.8, zorder=4)
        yy -= 0.34
    ax.plot([x - w/2, x + w/2], [yy + 0.13, yy + 0.13], color=BORDER, linewidth=1.0, zorder=4)
    for m in methods:
        ax.text(x - w/2 + 0.12, yy - 0.05, m, ha='left', va='center', fontsize=6.8, zorder=4)
        yy -= 0.34
    return h


def draw_class():
    fig, ax = new_ax(13, 9.5, 18, 14, '图4  云旅 App 分析类图')

    # Row 1：实体类（POI + 行程）
    class_box(ax, 2.0, 11.0, 'Attraction', '<<实体类>>',
              ['-name', '-address', '-ticketPrice:int', '-openTime', '-tags', '-features'],
              ['+fromJson()'])
    class_box(ax, 5.4, 11.0, 'Hotel', '<<实体类>>',
              ['-name', '-roomType', '-price:int', '-address', '-location'],
              ['+fromJson()'])
    class_box(ax, 8.8, 11.0, 'Food', '<<实体类>>',
              ['-name', '-cuisine', '-avgPrice:int', '-signature', '-tags'],
              ['+fromJson()'])
    class_box(ax, 12.2, 11.0, 'DayPlan', '<<实体类>>',
              ['-day:int', '-title', '-weather', '-attractions', '-foods'],
              [])
    class_box(ax, 15.6, 11.0, 'Plan', '<<实体类>>',
              ['-style', '-score:int', '-itinerary', '-totalDays:int'],
              ['+summary()'])

    # Row 2：业务层
    class_box(ax, 4.5, 6.2, 'PlanGenerator', '<<控制类>>',
              ['-styles', '-cityData'],
              ['+generatePlans()', '+scorePlan()', '+assignByDays()'])
    class_box(ax, 10.5, 6.2, 'TripPlanner', '<<控制类>>',
              ['-generator', '-ai', '-repo'],
              ['+createTrip()', '+fallbackLocal()', '+savePlan()'])
    class_box(ax, 15.5, 6.2, 'TripPreference', '<<实体类>>',
              ['-departure', '-destination', '-days:int', '-budget:int'],
              ['+toPrompt()'])

    # Row 3：网络层 + 数据层
    class_box(ax, 3.0, 2.6, 'DeepSeekService', '<<网络层>>',
              ['-apiKey', '-baseUrl', '-model'],
              ['+generatePlan()', '+available()', '+chat()'])
    class_box(ax, 8.8, 2.6, 'DataRepository', '<<数据层>>',
              ['-cities'],
              ['+loadCities()', '+getAttractions()', '+getHotels()', '+getFoods()'])
    class_box(ax, 14.5, 2.6, 'DatabaseService', '<<数据层>>',
              ['-db'],
              ['+savePlan()', '+queryPlans()', '+deletePlan()'])

    # ---- 关系 ----
    # Plan 组合 DayPlan（横向，实心菱形在整体 Plan 端）
    ax.plot([13.7, 14.05], [11.0, 11.0], color=BORDER, linewidth=1.3, zorder=2)
    ax.add_patch(Polygon([(14.05, 11.0), (14.18, 11.13), (14.31, 11.0), (14.18, 10.87)],
                         closed=True, facecolor=BORDER, edgecolor=BORDER, zorder=3))
    ax.text(13.85, 11.35, '1..*', fontsize=7, color=GRAY, ha='center')
    # TripPlanner 依赖 PlanGenerator
    arrow(ax, (9.0, 6.2), (6.0, 6.2), color=GRAY, ls='--')
    # TripPlanner 依赖 DeepSeekService / DataRepository
    arrow(ax, (10.5, 5.35), (4.5, 4.1), color=GRAY, ls='--')
    arrow(ax, (10.5, 5.3), (8.8, 4.15), color=GRAY, ls='--')
    # DataRepository 依赖实体类（向上虚线到 Food，代表读取 POI）
    arrow(ax, (8.8, 4.15), (8.8, 9.15), color=GRAY, ls='--')

    fig.savefig(OUT + 'uml_class.png', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)


# ==================== 5. 架构图 ====================
def layer_box(ax, y0, y1, title, boxes, box_h=0.9):
    ax.add_patch(Rectangle((0.4, y0), 11.2, y1 - y0, fill=True, facecolor=LIGHT2,
                           edgecolor=BORDER, linewidth=1.3, zorder=1))
    ax.text(0.6, y1 - 0.35, title, fontsize=11.5, fontweight='bold', color=BLUE, va='center', zorder=3)
    n = len(boxes)
    total_w = n * 1.75 + (n - 1) * 0.2
    x = (0.4 + 11.2 - total_w) / 2 + 0.875
    yc = (y0 + y1) / 2
    for label in boxes:
        ax.add_patch(FancyBboxPatch((x - 0.875, yc - box_h/2), 1.75, box_h,
                                    boxstyle='round,pad=0.02,rounding_size=0.12',
                                    facecolor='white', edgecolor=BORDER, linewidth=1.2, zorder=3))
        ax.text(x, yc, label, fontsize=8.3, ha='center', va='center', zorder=4)
        x += 1.75 + 0.2


def draw_architecture():
    fig, ax = new_ax(12, 7.5, 12, 8.5, '图5  云旅 App 三层架构图')

    layer_box(ax, 6.2, 8.0, 'UI 层', ['首页/城市', '需求录入', '方案列表', '行程详情', '行程编辑', '我的/设置'])
    layer_box(ax, 3.6, 5.4, '业务层', ['TripPlanner\n(门面)', 'PlanGenerator\n(规则引擎)', 'DeepSeekService\n(AI 增强)'])
    layer_box(ax, 1.0, 2.8, '数据层', ['DataRepository\n(JSON资源)', 'DatabaseService\n(SQLite)', 'PrefsService\n(偏好)', 'FileService\n(文件IO)'])

    arrow(ax, (6, 6.1), (6, 5.5), lw=1.6)
    arrow(ax, (6, 5.5), (6, 6.1), lw=1.6)
    arrow(ax, (6, 3.5), (6, 2.9), lw=1.6)
    arrow(ax, (6, 2.9), (6, 3.5), lw=1.6)
    ax.text(6.25, 5.8, '调用', fontsize=8.5, color=GRAY, va='center')
    ax.text(6.25, 3.2, '读写', fontsize=8.5, color=GRAY, va='center')

    ax.add_patch(FancyBboxPatch((9.6, 5.3), 2.2, 1.4, boxstyle='round,pad=0.02,rounding_size=0.12',
                                facecolor='#fff7e6', edgecolor=BORDER, linewidth=1.2, zorder=3))
    ax.text(10.7, 6.0, 'DeepSeek API', fontsize=8.5, ha='center', va='center', fontweight='bold')
    ax.text(10.7, 5.55, '(HTTP/JSON)', fontsize=7.5, ha='center', va='center', color=GRAY)
    arrow(ax, (9.6, 5.55), (8.9, 5.55), ls='--', color=GRAY)

    fig.savefig(OUT + 'uml_architecture.png', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)


if __name__ == '__main__':
    draw_use_case(); print('use_case done')
    draw_activity_generate(); print('activity_generate done')
    draw_activity_edit(); print('activity_edit done')
    draw_class(); print('class done')
    draw_architecture(); print('architecture done')
