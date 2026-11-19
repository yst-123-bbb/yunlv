import 'package:flutter/material.dart';

import '../routes.dart';
import '../services/storage_service.dart';
import '../services/trip_stops.dart';
import '../services/waypoints.dart';
import 'history_page.dart';
import 'home_page.dart';
import 'settings_page.dart';

/// 根框架：Drawer + BottomNavigationBar 双导航，TabBar 位于各子页。
class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _tab = 0;
  final ValueNotifier<int> _reloadTick = ValueNotifier(0);

  static const List<String> _titles = ['首页', '我的行程', '我的'];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _maybeShowOnboarding());
  }

  @override
  void dispose() {
    _reloadTick.dispose();
    super.dispose();
  }

  /// 首次进入引导：未完成过引导时弹窗提示完善个人信息。
  Future<void> _maybeShowOnboarding() async {
    final onboarded = await PrefsService.loadOnboarded();
    if (onboarded) return;
    await PrefsService.saveOnboarded(true);
    if (!mounted) return;
    final go = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Row(children: [
          Icon(Icons.waving_hand_outlined, color: Colors.teal),
          SizedBox(width: 8),
          Text('欢迎使用云旅 App'),
        ]),
        content: const Text('建议先完善个人信息（住址、口味偏好、预算等），这样生成的行程会更贴合你的需求。'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('稍后再说')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('去填写')),
        ],
      ),
    );
    if (go == true && mounted) {
      Navigator.of(context).pushNamed(Routes.settings);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_titles[_tab]),
        centerTitle: true,
        leading: Builder(
          builder: (context) => IconButton(
            icon: const Icon(Icons.menu),
            tooltip: '打开菜单',
            onPressed: () => Scaffold.of(context).openDrawer(),
          ),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.chat_bubble_outline),
            tooltip: 'AI 助手',
            onPressed: () {
              Navigator.of(context).pushNamed(Routes.chat);
            },
          ),
        ],
      ),
      drawer: _buildDrawer(context),
      body: IndexedStack(
        index: _tab,
        children: [
          const HomePage(),
          HistoryPage(reloadTick: _reloadTick),
          const SettingsPage(),
        ],
      ),
      floatingActionButton: _tab == 0
          ? FloatingActionButton.extended(
              onPressed: () {
                Navigator.of(context).pushNamed(
                  Routes.planChat,
                  arguments: (
                    cities: TripPlanStore.instance.items,
                    waypoints: WaypointStore.instance.items,
                  ),
                );
              },
              icon: const Icon(Icons.add_rounded),
              label: const Text('开始规划'),
            )
          : null,
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _tab,
        onTap: (i) {
          setState(() => _tab = i);
          // 切到「我的行程」时触发其刷新，避免保存后列表不更新
          if (i == 1) _reloadTick.value++;
        },
        type: BottomNavigationBarType.fixed,
        selectedItemColor: Theme.of(context).colorScheme.primary,
        unselectedItemColor: Colors.grey,
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.explore_outlined), activeIcon: Icon(Icons.explore), label: '首页'),
          BottomNavigationBarItem(icon: Icon(Icons.map_outlined), activeIcon: Icon(Icons.map), label: '我的行程'),
          BottomNavigationBarItem(icon: Icon(Icons.person_outline), activeIcon: Icon(Icons.person), label: '我的'),
        ],
      ),
    );
  }

  Widget _buildDrawer(BuildContext context) {
    return Drawer(
      child: ListView(
        padding: EdgeInsets.zero,
        children: [
          DrawerHeader(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  Theme.of(context).colorScheme.primary,
                  Theme.of(context).colorScheme.primaryContainer,
                ],
              ),
            ),
            child: const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                Icon(Icons.cloud_outlined, color: Colors.white, size: 40),
                SizedBox(height: 8),
                Text('云旅 App',
                    style: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold)),
                Text('智能旅行规划助手', style: TextStyle(color: Colors.white70, fontSize: 13)),
              ],
            ),
          ),
          _drawerTile(context, Icons.home_outlined, '首页', () {
            Navigator.pop(context);
            setState(() => _tab = 0);
          }),
          _drawerTile(context, Icons.chat_bubble_outline, 'AI 助手', () {
            Navigator.pop(context);
            Navigator.of(context).pushNamed(Routes.chat);
          }),
          _drawerTile(context, Icons.train_outlined, '交通查询', () {
            Navigator.pop(context);
            Navigator.of(context).pushNamed(Routes.transit);
          }),
          _drawerTile(context, Icons.history_outlined, '我的行程', () {
            Navigator.pop(context);
            setState(() => _tab = 1);
            _reloadTick.value++;
          }),
          _drawerTile(context, Icons.settings_outlined, '设置', () {
            Navigator.pop(context);
            setState(() => _tab = 2);
          }),
          const Divider(),
          _drawerTile(context, Icons.info_outline, '关于', () => _showAbout(context)),
        ],
      ),
    );
  }

  Widget _drawerTile(BuildContext context, IconData icon, String title, VoidCallback onTap) {
    return ListTile(
      leading: Icon(icon),
      title: Text(title),
      onTap: onTap,
    );
  }

  void _showAbout(BuildContext context) {
    Navigator.pop(context);
    showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Row(children: [Icon(Icons.cloud_outlined, color: Colors.teal), SizedBox(width: 8), Text('关于云旅 App')]),
        content: const Text(
          '云旅 App 是一款旅游规划助手：输入出行需求，即可生成多风格行程方案。\n\n'
          '核心特点：AI 优先（DeepSeek 增强）、本地兜底（规则引擎离线可用）。\n\n'
          '数据来源：本地结构化数据（景点/酒店/美食/交通）。\n版本：1.0.0',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('知道了')),
        ],
      ),
    );
  }
}
