import 'package:flutter/material.dart';

import '../config.dart';
import '../services/storage_service.dart';

/// 设置页：预算档位 / 默认出发地 / 口味偏好 / AI 开关（SharedPreferences 持久化）。
class SettingsPage extends StatefulWidget {
  const SettingsPage({super.key});

  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<SettingsPage> {
  String _budgetLevel = 'mid';
  bool _aiEnabled = true;
  bool _loaded = false;

  // 个人信息
  String _address = '';
  List<String> _tastes = [];
  List<String> _attractionPrefs = [];
  String _travelStyle = 'fast';
  int _accBudget = 0;
  int _transBudget = 0;
  int _totalBudget = 0;

  static const Map<String, String> _levelLabels = {'low': '经济型', 'mid': '舒适型', 'high': '高档型'};
  static const Map<String, String> _travelStyleLabels = {'fast': '特种兵 · 注重性价比', 'slow': '慢游 · 注重感受'};
  static const List<String> _attractionPrefOptions = [
    '人文古迹', '自然风光', '主题乐园', '美食文化', '网红打卡', '亲子休闲', '购物',
  ];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    _budgetLevel = await PrefsService.loadBudgetLevel();
    _aiEnabled = await PrefsService.loadAiEnabled();
    _address = await PrefsService.loadAddress();
    _tastes = await PrefsService.loadTastes();
    _attractionPrefs = await PrefsService.loadAttractionPref();
    _travelStyle = await PrefsService.loadTravelStyle();
    _accBudget = await PrefsService.loadAccommodationBudget();
    _transBudget = await PrefsService.loadTransportBudget();
    _totalBudget = await PrefsService.loadTotalBudget();
    if (mounted) setState(() => _loaded = true);
  }

  Future<void> _pickLevel() async {
    final keys = _levelLabels.keys.toList();
    final v = await showDialog<String>(
      context: context,
      builder: (ctx) => SimpleDialog(
        title: const Text('住宿预算档位'),
        children: [
          for (final k in keys)
            SimpleDialogOption(
              onPressed: () => Navigator.pop(ctx, k),
              child: Row(
                children: [
                  Icon(
                    k == _budgetLevel ? Icons.check_circle : Icons.circle_outlined,
                    size: 20,
                    color: k == _budgetLevel ? Theme.of(ctx).colorScheme.primary : Colors.grey,
                  ),
                  const SizedBox(width: 12),
                  Text(_levelLabels[k]!, style: const TextStyle(fontSize: 15)),
                ],
              ),
            ),
        ],
      ),
    );
    if (v != null) {
      await PrefsService.saveBudgetLevel(v);
      setState(() => _budgetLevel = v);
    }
  }

  /// 大概住址：文本输入
  Future<void> _pickAddress() async {
    final controller = TextEditingController(text: _address);
    final v = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('大概住址'),
        content: TextField(
          controller: controller,
          autofocus: true,
          maxLength: 30,
          decoration: const InputDecoration(hintText: '如：北京市朝阳区 / 杭州市西湖区'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
          TextButton(
            onPressed: () => Navigator.pop(ctx, controller.text.trim()),
            child: const Text('保存'),
          ),
        ],
      ),
    );
    if (v != null) {
      await PrefsService.saveAddress(v);
      setState(() => _address = v);
    }
  }

  /// 景点偏好：多选标签
  Future<void> _pickAttractionPref() async {
    final selected = Set<String>.of(_attractionPrefs);
    await showDialog<void>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialog) => AlertDialog(
          title: const Text('景点偏好（可多选）'),
          contentPadding: const EdgeInsets.symmetric(vertical: 8),
          content: SizedBox(
            width: double.maxFinite,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                for (final t in _attractionPrefOptions)
                  CheckboxListTile(
                    dense: true,
                    title: Text(t),
                    value: selected.contains(t),
                    onChanged: (v) => setDialog(() {
                      v == true ? selected.add(t) : selected.remove(t);
                    }),
                  ),
              ],
            ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
            TextButton(
              onPressed: () async {
                Navigator.pop(ctx);
                await PrefsService.saveAttractionPref(selected.toList());
                if (mounted) setState(() => _attractionPrefs = selected.toList());
              },
              child: const Text('保存'),
            ),
          ],
        ),
      ),
    );
  }

  /// 口味偏好：多选
  Future<void> _pickTastes() async {
    final selected = Set<String>.of(_tastes);
    await showDialog<void>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialog) => AlertDialog(
          title: const Text('口味偏好（可多选）'),
          contentPadding: const EdgeInsets.symmetric(vertical: 8),
          content: SizedBox(
            width: double.maxFinite,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                for (final e in AppConfig.tasteOptions.entries)
                  CheckboxListTile(
                    dense: true,
                    title: Text(e.value),
                    value: selected.contains(e.key),
                    onChanged: (v) => setDialog(() {
                      v == true ? selected.add(e.key) : selected.remove(e.key);
                    }),
                  ),
              ],
            ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
            TextButton(
              onPressed: () async {
                Navigator.pop(ctx);
                await PrefsService.saveTastes(selected.toList());
                if (mounted) setState(() => _tastes = selected.toList());
              },
              child: const Text('保存'),
            ),
          ],
        ),
      ),
    );
  }

  /// 一键清理个人信息
  Future<void> _clearPersonalInfo() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('清理个人信息'),
        content: const Text('将清除住址、口味、景点偏好、旅行风格及各类预算，且下次启动会再次提醒填写。确定继续？'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('取消')),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('清理', style: TextStyle(color: Colors.redAccent)),
          ),
        ],
      ),
    );
    if (ok == true) {
      await PrefsService.clearPersonalInfo();
      if (!mounted) return;
      setState(() {
        _address = '';
        _tastes = [];
        _attractionPrefs = [];
        _travelStyle = 'fast';
        _accBudget = 0;
        _transBudget = 0;
        _totalBudget = 0;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('个人信息已清理')),
      );
    }
  }

  /// 旅行风格：特种兵 / 慢游
  Future<void> _pickTravelStyle() async {
    final keys = _travelStyleLabels.keys.toList();
    final v = await showDialog<String>(
      context: context,
      builder: (ctx) => SimpleDialog(
        title: const Text('旅行风格偏好'),
        children: [
          for (final k in keys)
            SimpleDialogOption(
              onPressed: () => Navigator.pop(ctx, k),
              child: Row(
                children: [
                  Icon(
                    k == _travelStyle ? Icons.check_circle : Icons.circle_outlined,
                    size: 20,
                    color: k == _travelStyle ? Theme.of(ctx).colorScheme.primary : Colors.grey,
                  ),
                  const SizedBox(width: 12),
                  Expanded(child: Text(_travelStyleLabels[k]!, style: const TextStyle(fontSize: 15))),
                ],
              ),
            ),
        ],
      ),
    );
    if (v != null) {
      await PrefsService.saveTravelStyle(v);
      setState(() => _travelStyle = v);
    }
  }

  /// 数字预算输入（住宿/出行/总预算共用）
  Future<void> _editBudget(
    String title,
    int current,
    Future<void> Function(int) save,
    ValueChanged<int> apply,
  ) async {
    final controller = TextEditingController(text: current == 0 ? '' : '$current');
    final v = await showDialog<int>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(title),
        content: TextField(
          controller: controller,
          autofocus: true,
          keyboardType: TextInputType.number,
          decoration: const InputDecoration(hintText: '输入金额（元），0 表示不限制'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
          TextButton(
            onPressed: () => Navigator.pop(ctx, int.tryParse(controller.text.trim()) ?? 0),
            child: const Text('保存'),
          ),
        ],
      ),
    );
    if (v != null) {
      await save(v);
      apply(v);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!_loaded) {
      return const Center(child: CircularProgressIndicator());
    }
    final body = _buildBody();
    // 作为独立路由被 push 时（首启引导 / 首页提醒横幅）提供 AppBar + 返回键；
    // 作为 HomeShell 的「我的」tab 时（无上级路由）不重复套 AppBar。
    if (!Navigator.of(context).canPop()) {
      return body;
    }
    return Scaffold(
      appBar: AppBar(title: const Text('设置')),
      body: body,
    );
  }

  Widget _buildBody() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _sectionCard('个人信息', [
          ListTile(
            leading: const Icon(Icons.home_outlined, color: Colors.teal),
            title: const Text('大概住址'),
            subtitle: const Text('同时作为默认出发地，非精确地址'),
            trailing: Text(
              _address.isEmpty ? '未填写' : _address,
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: _address.isEmpty ? Colors.grey : Colors.black87,
              ),
            ),
            onTap: _pickAddress,
          ),
          ListTile(
            leading: const Icon(Icons.attractions_outlined, color: Colors.teal),
            title: const Text('景点偏好'),
            subtitle: Text(_attractionPrefs.isEmpty ? '未选择' : _attractionPrefs.join('、')),
            trailing: const Icon(Icons.chevron_right, color: Colors.grey),
            onTap: _pickAttractionPref,
          ),
          ListTile(
            leading: const Icon(Icons.directions_walk_outlined, color: Colors.teal),
            title: const Text('旅行风格偏好'),
            subtitle: const Text('影响方案节奏与风格排序'),
            trailing: Text(_travelStyleLabels[_travelStyle]!, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
            onTap: _pickTravelStyle,
          ),
          ListTile(
            leading: const Icon(Icons.restaurant_outlined, color: Colors.teal),
            title: const Text('口味偏好'),
            subtitle: Text(_tastes.isEmpty ? '未选择' : _tastes.map((k) => AppConfig.tasteOptions[k] ?? k).join('、')),
            trailing: const Icon(Icons.chevron_right, color: Colors.grey),
            onTap: _pickTastes,
          ),
          const Divider(height: 1),
          ListTile(
            leading: const Icon(Icons.hotel_outlined, color: Colors.teal),
            title: const Text('住宿预算'),
            subtitle: const Text('每晚住宿上限（元）'),
            trailing: Text(_accBudget == 0 ? '不限制' : '¥$_accBudget', style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
            onTap: () => _editBudget('住宿预算（元）', _accBudget, PrefsService.saveAccommodationBudget, (v) => setState(() => _accBudget = v)),
          ),
          ListTile(
            leading: const Icon(Icons.directions_transit_outlined, color: Colors.teal),
            title: const Text('出行预算'),
            subtitle: const Text('往返交通预算（元）'),
            trailing: Text(_transBudget == 0 ? '不限制' : '¥$_transBudget', style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
            onTap: () => _editBudget('出行预算（元）', _transBudget, PrefsService.saveTransportBudget, (v) => setState(() => _transBudget = v)),
          ),
          ListTile(
            leading: const Icon(Icons.account_balance_wallet_outlined, color: Colors.teal),
            title: const Text('总预算上限'),
            subtitle: const Text('人均总花费上限（元）'),
            trailing: Text(_totalBudget == 0 ? '不限制' : '¥$_totalBudget', style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
            onTap: () => _editBudget('总预算上限（元）', _totalBudget, PrefsService.saveTotalBudget, (v) => setState(() => _totalBudget = v)),
          ),
          ListTile(
            leading: const Icon(Icons.hotel_outlined, color: Colors.teal),
            title: const Text('住宿预算档位'),
            subtitle: const Text('影响方案中酒店的选择'),
            trailing: Text(_levelLabels[_budgetLevel]!, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
            onTap: _pickLevel,
          ),
          const Divider(height: 1),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 14),
            child: Align(
              alignment: Alignment.centerLeft,
              child: TextButton.icon(
                onPressed: _clearPersonalInfo,
                icon: const Icon(Icons.delete_sweep_outlined, size: 18),
                label: const Text('一键清理个人信息'),
                style: TextButton.styleFrom(foregroundColor: Colors.redAccent),
              ),
            ),
          ),
        ]),
        const SizedBox(height: 12),
        _sectionCard('AI 智能', [
          SwitchListTile(
            secondary: const Icon(Icons.auto_awesome, color: Colors.orange),
            title: const Text('启用 AI 智能行程'),
            subtitle: Text(
              AppConfig.deepseekEnabled
                  ? '使用 DeepSeek 生成智能行程（本地兜底）'
                  : '未配置 API Key，AI 增强不可用（仅本地规则引擎）',
            ),
            value: _aiEnabled && AppConfig.deepseekEnabled,
            onChanged: AppConfig.deepseekEnabled
                ? (v) async {
                    await PrefsService.saveAiEnabled(v);
                    setState(() => _aiEnabled = v);
                  }
                : null,
          ),
        ]),
        const SizedBox(height: 12),
        _sectionCard('关于', [
          const ListTile(
            leading: Icon(Icons.cloud_outlined, color: Colors.teal),
            title: Text('云旅 App'),
            subtitle: Text('AI 优先 · 本地兜底的旅行规划助手'),
            trailing: Text('v1.0.0', style: TextStyle(color: Colors.grey)),
          ),
          const ListTile(
            leading: Icon(Icons.info_outline, color: Colors.teal),
            title: Text('数据说明'),
            subtitle: Text('景点 / 酒店 / 美食 / 交通数据均来自本地结构化 JSON，离线可用'),
          ),
        ]),
      ],
    );
  }

  Widget _sectionCard(String title, List<Widget> children) {
    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 4),
            child: Text(title, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
          ),
          ...children,
        ],
      ),
    );
  }
}
