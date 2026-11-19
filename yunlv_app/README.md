# 云旅 App —— Flutter 旅游规划助手

基于「云旅AI」的 Flutter 重制版：用户输入出行需求，App 自动生成多风格行程方案。
**AI 优先、本地兜底**——联网时调用 DeepSeek 生成智能行程，断网 / 无 Key / 超时自动回退本地规则引擎，业务闭环不中断。

> 本工程对应《Flutter 课程大作业》，配套文档见 `docs/功能模块清单.md`，UML 图见 `diagrams/`。

## 一、功能总览

| 模块 | 说明 |
|------|------|
| 省份城市浏览 | 20 个热门城市按「省份 → 城市」分组 + 搜索（Wrap / Hero） |
| 景点推荐与途经地 | 城市 → 景点推荐（含网络示意图片）→ 景点详情，可把想去的景点加入「途经地」 |
| 多目的地 | **长按城市**加入行程，游玩天数按各景点游玩时长自动估算，方案按城逐日编排 |
| 需求录入 | 出发地、多目的地、日期、人数、人群、口味（多选）、住宿预算、交通偏好、人均预算自由填写、跨城班次选择 |
| 方案生成 | 本地规则引擎生成多种风格方案并附「推荐语」（取消评分）；天数自动估算 + 途经地优先 + 个人信息偏置；DeepSeek AI 增强 |
| 完整费用估算 | 人均预算含门票 + 一天三餐 + 住宿 + 交通（市内 + 跨城班次）明细与合计 |
| AI 对话 | 首页醒目 AI 横幅入口 + 聊天对话；「开始规划」进入 AI 对话式行程定制（同步首页站点/途经地/个人信息，支持游玩时间校验） |
| 方案浏览 | 多方案列表、方案详情、逐日行程、天气 / 餐饮 / 住宿 |
| 行程编辑 | 增删景点、拖拽排序、预算实时统计（ReorderableListView + Listener） |
| 历史行程 | 「我的行程」豆包式布局（左历史方案列表 + 右 AI 对话），SQLite 持久化历史行程，删除 / 清空 |
| 行程导出 | 导出 .txt / .json 行程单（File IO） |
| 个人信息与偏好 | 大概住址、口味（10 项多选）、景点偏好、旅行风格（特种兵/慢游）、三档预算；首启引导填写 + 一键清理（SharedPreferences） |
| 交通查询 | 高铁车次 / 航班方案（舱位价格）本地结构化数据；规划时可选具体班次 |

## 二、课程知识点覆盖

- **布局**：Row / Column / Flex / GridView / Wrap / Stack
- **组件**：StatefulWidget / StatelessWidget
- **导航**：BottomNavigationBar + TabBar + Drawer 三套导航
- **弹窗**：AlertDialog（删除确认 / 首启引导 / 清理确认）+ SimpleDialog（城市 / 预算 / 班次选择）
- **手势**：GestureDetector（卡片点击 / **城市卡长按加入行程**）+ Listener（预算头指针监听）
- **动画**：隐式动画（AnimatedContainer / AnimatedSize）+ 显式动画（RotationTransition/ScaleTransition 加载指示器）+ Hero 共享动画（城市卡 / 方案卡）
- **网络**：HTTP 请求（DeepSeek）+ JSON 编解码 + try-catch 异常处理 + Image.network（景点示意图片，errorBuilder 兜底）
- **持久化**：File IO（导出）+ SharedPreferences（偏好）+ SQLite（历史）
- **多平台**：Windows（exe）+ Web（Edge 网页），共用同一套代码（android/ 已就绪，装 SDK 即可打 APK）

## 三、目录结构

```
lib/
├── main.dart              # 入口 + Splash + HomeShell（Drawer + BottomNav + AI 助手入口）
├── config.dart            # AppConfig（DeepSeek Key / 偏好键名）
├── models/models.dart     # 数据模型（fromJson / toJson / ChatMessage）
├── services/
│   ├── data_repository.dart   # 本地 JSON 加载与查询（省份分组）
│   ├── plan_generator.dart    # 规则引擎（多风格生成 + 多城市 + 途经地优先）
│   ├── transit_service.dart   # 高铁 / 航班查询
│   ├── deepseek_service.dart  # DeepSeek AI 增强（行程生成 + AI 对话，数据注入 + 降级）
│   ├── waypoints.dart         # 途经地状态单例（ValueNotifier）
│   ├── trip_stops.dart        # 行程站点状态单例（城市列表，ValueNotifier）
│   ├── storage_service.dart   # PrefsService + 条件导出（io/web 分流）
│   ├── storage_io.dart        # 桌面：dart:io + SQLite
│   ├── storage_web.dart       # Web：浏览器下载 + localStorage
│   └── plan_text.dart         # 行程单文本生成（io/web 共用）
├── pages/                 # 各页面（含 city_detail / attraction_detail / chat）
└── widgets/common.dart    # 公共小组件（加载动画 / 星级 / 标签 / 景点图片 AttractionImage）
assets/data/               # 景点 / 酒店 / 美食 / 城市 / 交通 JSON
docs/                      # 功能模块清单
diagrams/                  # 5 张 UML 图
```

## 四、运行与构建

```bash
flutter pub get
flutter run               # 运行（Windows 桌面 / 浏览器 / 模拟器）
flutter test              # 单元测试
flutter build windows     # 打包 exe（输出 build/windows/x64/runner/Release/）
flutter build web         # 打包网页（输出 build/web/，可用 Edge/Chrome 打开）
flutter build apk         # 打包 APK（需先安装 Android Studio / SDK）
```

- Windows 运行目录为 `build/windows/x64/runner/Release/`，其中 `yunlv_app.exe` 为可执行入口，需与同目录的 `flutter_windows.dll`、`data/` 等一起分发。
- Web 构建产物为 `build/web/`，可用 `flutter run -d edge` 或本地静态服务器打开 `index.html`。
- 本工程已支持 **Windows（exe）+ Web（Edge）** 双平台打包，满足「≥2 平台」要求；
  Android APK 因本机未装 SDK 暂未构建，装好 Android Studio 后执行 `flutter build apk` 即可。

> 跨平台存储说明：`lib/services/` 采用「条件导出」实现平台分流——
> 桌面端用 `dart:io` + SQLite（`storage_io.dart`），Web 端用浏览器下载 + localStorage（`storage_web.dart`），
> 对外 API 完全一致，业务代码无需感知平台差异。

## 五、DeepSeek AI 配置

在 `lib/config.dart` 中填入你的 DeepSeek API Key：

```dart
static const String deepseekApiKey = 'sk-...';  // 留空则关闭 AI 增强，仅本地引擎
```

- 填 Key 后，「AI 智能行程」与「AI 助手」对话（询问景点信息）都会走 DeepSeek。
- AI 对话会把本地景点数据注入上下文，基于真实数据作答；无 Key / 断网 / 超时自动降级。

> 注意：**提交作业前如不想泄露密钥，可将此处置空**（置空后 App 仍离线可用，仅 AI 增强与 AI 对话不可用）。

## 六、数据说明

景点 / 酒店 / 美食 / 交通数据均来自「云旅AI」Python 版本地数据迁移（`tools/migrate_data.py`），
无实时数据 API，全部离线可用。
