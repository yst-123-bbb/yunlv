import 'package:flutter/material.dart';

import '../models/models.dart';
import '../services/deepseek_service.dart';

/// 可复用的 AI 对话面板（不含 Scaffold / AppBar），
/// 供 [ChatPage] 与「我的行程」右栏共用，避免重复实现。
class AiChatView extends StatefulWidget {
  final String context; // 注入 AI 的本地景点数据上下文
  final String? seedQuestion; // 进入时自动发送的问题（可选）
  final String hintText;
  final String welcomeTitle;
  final String welcomeSubtitle;
  final String fallbackText; // AI 不可用时的兜底文案

  const AiChatView({
    super.key,
    required this.context,
    this.seedQuestion,
    this.hintText = '问问景点信息…',
    this.welcomeTitle = '云旅小助手',
    this.welcomeSubtitle = '想问什么都可以，比如：\n「故宫门票多少钱？」「大理有什么必玩景点？」',
    this.fallbackText = 'AI 暂时不可用，请检查网络或稍后再试。',
  });

  @override
  State<AiChatView> createState() => _AiChatViewState();
}

class _AiChatViewState extends State<AiChatView> {
  final TextEditingController _input = TextEditingController();
  final ScrollController _scroll = ScrollController();
  final List<ChatMessage> _messages = [];
  bool _loading = false;

  @override
  void initState() {
    super.initState();
    if (widget.seedQuestion != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _send(widget.seedQuestion!));
    }
  }

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _send(String text) async {
    final q = text.trim();
    if (q.isEmpty || _loading) return;
    setState(() => _messages.add(ChatMessage(role: 'user', content: q)));
    _input.clear();
    _scrollToBottom();

    setState(() => _loading = true);
    final reply = await DeepSeekService.chat(List.of(_messages), context: widget.context);
    if (!mounted) return;
    setState(() {
      _loading = false;
      _messages.add(ChatMessage(role: 'assistant', content: reply ?? widget.fallbackText));
    });
    _scrollToBottom();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.animateTo(
          _scroll.position.maxScrollExtent,
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Expanded(
          child: _messages.isEmpty && !_loading
              ? _welcome()
              : ListView.builder(
                  controller: _scroll,
                  padding: const EdgeInsets.all(16),
                  itemCount: _messages.length + (_loading ? 1 : 0),
                  itemBuilder: (_, i) {
                    if (i == _messages.length) return const _TypingBubble();
                    return _bubble(_messages[i]);
                  },
                ),
        ),
        _inputBar(),
      ],
    );
  }

  Widget _welcome() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.auto_awesome, size: 52, color: Colors.teal),
            const SizedBox(height: 12),
            Text(widget.welcomeTitle, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 6),
            Text(
              widget.welcomeSubtitle,
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.grey[600], height: 1.6),
            ),
          ],
        ),
      ),
    );
  }

  Widget _bubble(ChatMessage m) {
    final isUser = m.role == 'user';
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.78),
        decoration: BoxDecoration(
          color: isUser ? Theme.of(context).colorScheme.primary : Colors.white,
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(16),
            topRight: const Radius.circular(16),
            bottomLeft: Radius.circular(isUser ? 16 : 4),
            bottomRight: Radius.circular(isUser ? 4 : 16),
          ),
        ),
        child: Text(
          m.content,
          style: TextStyle(color: isUser ? Colors.white : Colors.black87, height: 1.5),
        ),
      ),
    );
  }

  Widget _inputBar() {
    return SafeArea(
      top: false,
      child: Container(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
        decoration: BoxDecoration(color: Colors.white, boxShadow: [
          BoxShadow(color: Colors.black.withValues(alpha: 0.05), blurRadius: 6),
        ]),
        child: Row(
          children: [
            Expanded(
              child: TextField(
                controller: _input,
                textInputAction: TextInputAction.send,
                onSubmitted: _send,
                decoration: InputDecoration(
                  hintText: widget.hintText,
                  filled: true,
                  fillColor: const Color(0xFFF2F4F7),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(24),
                    borderSide: BorderSide.none,
                  ),
                  contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                ),
              ),
            ),
            const SizedBox(width: 8),
            IconButton.filled(
              onPressed: _loading ? null : () => _send(_input.text),
              icon: const Icon(Icons.send_rounded),
              tooltip: '发送',
            ),
          ],
        ),
      ),
    );
  }
}

/// AI 正在输入的气泡
class _TypingBubble extends StatelessWidget {
  const _TypingBubble();

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
        ),
        child: const SizedBox(
          width: 18,
          height: 18,
          child: CircularProgressIndicator(strokeWidth: 2),
        ),
      ),
    );
  }
}
