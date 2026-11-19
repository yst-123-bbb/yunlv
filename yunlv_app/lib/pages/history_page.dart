import 'dart:convert';

import 'package:flutter/material.dart';

import '../models/models.dart';
import '../routes.dart';
import '../services/data_repository.dart';
import '../services/storage_service.dart';
import '../widgets/ai_chat_view.dart';
import '../widgets/common.dart';

/// 我的行程页（豆包式布局）：左侧为历史方案列表，右侧为 AI 对话区。
///
/// 历史方案存于 SQLite；点击左侧卡片打开方案详情。切换到底部「我的行程」tab 时
/// 由 [reloadTick] 触发刷新，解决「保存后列表不刷新」的问题。
class HistoryPage extends StatefulWidget {
  final ValueNotifier<int>? reloadTick;
  const HistoryPage({super.key, this.reloadTick});

  @override
  State<HistoryPage> createState() => HistoryPageState();
}

class HistoryPageState extends State<HistoryPage> {
  List<Map<String, dynamic>> _history = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    widget.reloadTick?.addListener(_reload);
    _reload();
  }

  @override
  void dispose() {
    widget.reloadTick?.removeListener(_reload);
    super.dispose();
  }

  Future<void> _reload() async {
    try {
      final h = await DatabaseService.queryHistory();
      if (!mounted) return;
      setState(() {
        _history = h;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _history = [];
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _historyPanel(),
        VerticalDivider(width: 1, thickness: 1, color: Colors.grey.shade200),
        Expanded(child: AiChatView(context: _buildContext())),
      ],
    );
  }

  String _buildContext() {
    final repo = DataRepository.instance;
    final buf = StringBuffer();
    for (final c in repo.cities) {
      final attrs = repo.attractionsOf(c.name);
      if (attrs.isEmpty) continue;
      buf.writeln('${c.name}（${c.province}）：${attrs.take(5).map((a) => a.name).join('、')}');
    }
    return buf.toString();
  }

  // ---------- 左侧历史方案栏 ----------

  Widget _historyPanel() {
    return Container(
      width: 270,
      color: Colors.white.withValues(alpha: 0.5),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 6),
            child: Row(
              children: [
                const Icon(Icons.history, size: 20, color: Colors.teal),
                const SizedBox(width: 8),
                const Text('历史方案', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
                const SizedBox(width: 6),
                Text('${_history.length}',
                    style: TextStyle(fontSize: 12, color: Colors.grey[600])),
                const Spacer(),
                if (_history.isNotEmpty)
                  TextButton(
                    onPressed: _confirmClearHistory,
                    child: const Text('清空', style: TextStyle(fontSize: 12)),
                  ),
              ],
            ),
          ),
          const Divider(height: 1),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _history.isEmpty
                    ? const EmptyPlaceholder(
                        icon: Icons.map_outlined,
                        text: '还没有保存的行程\n生成方案后点击「保存到我的行程」',
                      )
                    : RefreshIndicator(
                        onRefresh: _reload,
                        child: ListView.builder(
                          physics: const AlwaysScrollableScrollPhysics(),
                          padding: const EdgeInsets.fromLTRB(8, 8, 8, 16),
                          itemCount: _history.length,
                          itemBuilder: (_, i) => _historyCard(_history[i]),
                        ),
                      ),
          ),
        ],
      ),
    );
  }

  Widget _historyCard(Map<String, dynamic> row) {
    final city = row['city'] ?? '';
    final style = row['style_name'] ?? '';
    final recommendation = row['recommendation'] ?? '';
    final days = row['days'] ?? 0;
    final date = (row['created_at'] ?? '').toString().split('.').first;
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 5),
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
        leading: CircleAvatar(
          backgroundColor: Colors.teal.shade50,
          child: const Icon(Icons.travel_explore, color: Colors.teal),
        ),
        title: Text('$city · $style', style: const TextStyle(fontSize: 14)),
        subtitle: Text(
          recommendation.isEmpty ? '$days 天 · $date' : '$recommendation · $days 天 · $date',
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(fontSize: 12),
        ),
        trailing: IconButton(
          icon: const Icon(Icons.delete_outline, color: Colors.redAccent, size: 20),
          onPressed: () => _confirmDeleteHistory(row),
        ),
        onTap: () => _openPlan(row),
        onLongPress: () => _confirmDeleteHistory(row),
      ),
    );
  }

  Future<void> _openPlan(Map<String, dynamic> row) async {
    try {
      final json = jsonDecode(row['plan_json'] as String) as Map<String, dynamic>;
      final plan = Plan.fromJson(json);
      if (!mounted) return;
      Navigator.of(context).pushNamed(
        Routes.planDetail,
        arguments: (
          plan: plan,
          city: row['city'] as String,
          budget: 0,
          historyId: (row['id'] as num?)?.toInt(),
        ),
      );
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('行程数据解析失败')));
    }
  }

  Future<void> _confirmDeleteHistory(Map<String, dynamic> row) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('删除行程'),
        content: Text('确定删除「${row['city']} · ${row['style_name']}」吗？'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('取消')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('删除')),
        ],
      ),
    );
    if (ok == true) {
      await DatabaseService.deleteHistory((row['id'] as num).toInt());
      _reload();
    }
  }

  Future<void> _confirmClearHistory() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('清空历史'),
        content: const Text('确定清空全部历史方案吗？此操作不可恢复。'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('取消')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('清空')),
        ],
      ),
    );
    if (ok == true) {
      await DatabaseService.clearHistory();
      _reload();
    }
  }
}
