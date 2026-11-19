import 'dart:math' as math;

import 'package:flutter/material.dart';

/// 公共小组件

/// 显式动画加载指示器：AnimationController 驱动的旋转 + 脉冲文字。
class LoadingSpinner extends StatefulWidget {
  final String message;
  const LoadingSpinner({super.key, this.message = '加载中…'});

  @override
  State<LoadingSpinner> createState() => _LoadingSpinnerState();
}

class _LoadingSpinnerState extends State<LoadingSpinner>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 900),
  )..repeat();

  late final Animation<double> _pulse =
      Tween<double>(begin: 0.85, end: 1.15).animate(
    CurvedAnimation(parent: _controller, curve: Curves.easeInOut),
  );

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final primary = Theme.of(context).colorScheme.primary;
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        RotationTransition(
          turns: _controller,
          child: Icon(Icons.airplanemode_active, size: 44, color: primary),
        ),
        const SizedBox(height: 16),
        ScaleTransition(
          scale: _pulse,
          child: Text(widget.message,
              style: TextStyle(color: primary, fontSize: 15, fontWeight: FontWeight.w600)),
        ),
      ],
    );
  }
}

/// 星级评分（由 rating 数值渲染）
class StarRating extends StatelessWidget {
  final double rating;
  final double size;
  const StarRating({super.key, required this.rating, this.size = 15});

  @override
  Widget build(BuildContext context) {
    final full = rating.round();
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        for (var i = 0; i < 5; i++)
          Icon(
            i < full ? Icons.star_rounded : Icons.star_outline_rounded,
            size: size,
            color: Colors.amber,
          ),
        const SizedBox(width: 4),
        Text(
          rating.toStringAsFixed(1),
          style: TextStyle(fontSize: size - 2, color: Colors.grey[700]),
        ),
      ],
    );
  }
}

/// 标签胶囊
class TagChip extends StatelessWidget {
  final String label;
  final Color color;
  const TagChip({super.key, required this.label, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(label, style: TextStyle(fontSize: 11, color: color, fontWeight: FontWeight.w600)),
    );
  }
}

/// 小节标题
class SectionTitle extends StatelessWidget {
  final String title;
  const SectionTitle({super.key, required this.title});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(4, 16, 4, 8),
      child: Text(title,
          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
    );
  }
}

/// 空状态占位
class EmptyPlaceholder extends StatelessWidget {
  final IconData icon;
  final String text;
  const EmptyPlaceholder({super.key, required this.icon, required this.text});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 56, color: Colors.grey[400]),
          const SizedBox(height: 12),
          Text(text, style: TextStyle(color: Colors.grey[500], fontSize: 14)),
        ],
      ),
    );
  }
}

/// 景点图片：网络示意图片（picsum.photos 按景点名生成稳定图片）。
/// 断网 / 加载失败时回退到「渐变 + 主题图标」封面，保证离线可用。
class AttractionImage extends StatelessWidget {
  final String name;
  final List<String> tags;
  final double height;
  final double? width;

  const AttractionImage({
    super.key,
    required this.name,
    this.tags = const [],
    required this.height,
    this.width,
  });

  IconData get _icon {
    if (tags.contains('人文古迹')) return Icons.account_balance;
    if (tags.contains('自然风光')) return Icons.landscape;
    if (tags.contains('主题乐园')) return Icons.attractions;
    if (tags.contains('美食文化')) return Icons.restaurant;
    if (tags.contains('购物')) return Icons.shopping_bag;
    if (tags.contains('网红打卡')) return Icons.photo_camera;
    if (tags.contains('亲子休闲')) return Icons.child_friendly;
    return Icons.photo;
  }

  Color get _color {
    const palette = [
      Color(0xFF00897B),
      Color(0xFF5C6BC0),
      Color(0xFFEC407A),
      Color(0xFF26A69A),
      Color(0xFF7E57C2),
      Color(0xFFEF6C00),
    ];
    final seed = tags.isEmpty ? name : tags.first;
    return palette[seed.hashCode.abs() % palette.length];
  }

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(12),
      child: SizedBox(
        width: width,
        height: height,
        child: Image.network(
          'https://picsum.photos/seed/${Uri.encodeComponent(name)}/600/400',
          fit: BoxFit.cover,
          width: width,
          height: height,
          loadingBuilder: (context, child, progress) {
            if (progress == null) return child;
            return Container(
              color: const Color(0xFFEEF0F3),
              child: const Center(child: CircularProgressIndicator(strokeWidth: 2)),
            );
          },
          errorBuilder: (context, error, stackTrace) => _fallback(),
        ),
      ),
    );
  }

  Widget _fallback() {
    final c = _color;
    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [c.withValues(alpha: 0.85), c.withValues(alpha: 0.55)],
        ),
      ),
      child: Center(child: Icon(_icon, color: Colors.white, size: height * 0.4)),
    );
  }
}

/// 预算环形图：用 [CustomPaint] 绘制各开销占比环，配合 [TweenAnimationBuilder]
/// 隐式动画从 0 展开到完整比例。中间显示人均合计。
class BudgetDonutChart extends StatelessWidget {
  final List<({String label, int value, Color color})> items;
  const BudgetDonutChart({super.key, required this.items});

  @override
  Widget build(BuildContext context) {
    final total = items.fold<int>(0, (s, e) => s + e.value);
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        TweenAnimationBuilder<double>(
          tween: Tween(begin: 0, end: 1),
          duration: const Duration(milliseconds: 800),
          curve: Curves.easeOutCubic,
          builder: (_, t, _) => CustomPaint(
            size: const Size(150, 150),
            painter: _DonutPainter(
              progress: t,
              values: [for (final e in items) e.value.toDouble()],
              colors: [for (final e in items) e.color],
            ),
            child: Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text('¥$total',
                      style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                  Text('人均合计', style: TextStyle(fontSize: 11, color: Colors.grey[600])),
                ],
              ),
            ),
          ),
        ),
        const SizedBox(height: 12),
        Wrap(
          spacing: 12,
          runSpacing: 6,
          alignment: WrapAlignment.center,
          children: [
            for (final e in items)
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    width: 10,
                    height: 10,
                    decoration: BoxDecoration(color: e.color, shape: BoxShape.circle),
                  ),
                  const SizedBox(width: 4),
                  Text('${e.label} ¥${e.value}',
                      style: TextStyle(fontSize: 12, color: Colors.grey[700])),
                ],
              ),
          ],
        ),
      ],
    );
  }
}

/// 环形图 painter：画灰色底环 + 各开销段弧，[progress] 驱动动画展开。
class _DonutPainter extends CustomPainter {
  final double progress;
  final List<double> values;
  final List<Color> colors;

  _DonutPainter({required this.progress, required this.values, required this.colors});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = (size.shortestSide - 24) / 2;
    const stroke = 18.0;

    final base = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke
      ..color = Colors.grey.shade200;
    canvas.drawCircle(center, radius, base);

    final total = values.fold<double>(0, (s, v) => s + v);
    if (total <= 0) return;

    var start = -math.pi / 2;
    final sweepTotal = 2 * math.pi * progress;
    for (var i = 0; i < values.length; i++) {
      if (values[i] <= 0) continue;
      final sweep = sweepTotal * (values[i] / total);
      final paint = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = stroke
        ..strokeCap = StrokeCap.butt
        ..color = colors[i];
      canvas.drawArc(Rect.fromCircle(center: center, radius: radius), start, sweep, false, paint);
      start += sweep;
    }
  }

  @override
  bool shouldRepaint(_DonutPainter oldDelegate) =>
      oldDelegate.progress != progress ||
      oldDelegate.values.length != values.length ||
      oldDelegate.colors.length != colors.length;
}
