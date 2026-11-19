import 'package:flutter/material.dart';

import '../models/models.dart';
import '../services/data_repository.dart';
import '../widgets/ai_chat_view.dart';

/// AI 对话页：用户可直接与「云旅小助手」沟通，询问景点相关信息。
///
/// 通过 [AiChatView] 调用 DeepSeek，并把本地真实景点数据注入上下文，
/// 让 AI 基于真实数据作答。可选 [about] 指定进入时就某个景点发问。
class ChatPage extends StatefulWidget {
  final Attraction? about;

  const ChatPage({super.key, this.about});

  @override
  State<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends State<ChatPage> {
  @override
  Widget build(BuildContext context) {
    final about = widget.about;
    return Scaffold(
      appBar: AppBar(title: const Text('AI 助手')),
      body: AiChatView(
        context: _buildContext(about),
        seedQuestion: about == null
            ? null
            : '介绍一下「${about.name}」吧，门票、开放时间、特色亮点都说说。',
      ),
    );
  }

  /// 构造注入 AI 的本地景点数据上下文（针对某景点时给出完整字段）。
  String _buildContext(Attraction? about) {
    final repo = DataRepository.instance;
    if (about != null) {
      final city = _cityOf(about.name);
      final buf = StringBuffer();
      buf.writeln('【用户正在咨询的景点】');
      buf.writeln('- 名称：${about.name}（$city）');
      buf.writeln('- 地址：${about.address}');
      buf.writeln('- 门票：${about.isFree ? '免费' : '$about.ticketPrice元'}');
      buf.writeln('- 开放时间：${about.openTime}');
      buf.writeln('- 特色：${about.features}');
      buf.writeln('- 贴士：${about.tips}');
      buf.writeln('- 标签：${about.tags.join('、')}${about.indoor ? '、室内' : ''}');
      return buf.toString();
    }

    final buf = StringBuffer();
    for (final c in repo.cities) {
      final attrs = repo.attractionsOf(c.name);
      if (attrs.isEmpty) continue;
      buf.writeln('${c.name}（${c.province}）：${attrs.take(5).map((a) => a.name).join('、')}');
    }
    return buf.toString();
  }

  /// 反查景点所属城市（用于上下文展示）。
  String _cityOf(String name) {
    final repo = DataRepository.instance;
    for (final c in repo.cities) {
      if (repo.attractionsOf(c.name).any((a) => a.name == name)) return c.name;
    }
    return '';
  }
}
