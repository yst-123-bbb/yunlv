import 'package:flutter/material.dart';

import 'routes.dart';
import 'services/data_repository.dart';
import 'widgets/common.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const YunLvApp());
}

/// 应用入口
class YunLvApp extends StatelessWidget {
  const YunLvApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '云旅 App',
      debugShowCheckedModeBanner: false,
      // 命名路由：集中式路由表（见 routes.dart）
      onGenerateRoute: Routes.onGenerateRoute,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF00897B)),
        scaffoldBackgroundColor: const Color(0xFFF6F8FA),
        // 指定中文字体，避免在 Windows 上中文回退到默认字体导致的缺字/乱码。
        fontFamily: 'Microsoft YaHei',
        fontFamilyFallback: const ['PingFang SC', 'Noto Sans CJK SC', 'SimHei'],
      ),
      home: const SplashScreen(),
    );
  }
}

/// 启动页：加载本地 JSON 数据（含显式旋转动画 + 错误兜底）。
class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {
  @override
  void initState() {
    super.initState();
    _bootstrap();
  }

  Future<void> _bootstrap() async {
    await DataRepository.instance.load();
    if (!mounted) return;
    Navigator.of(context).pushReplacementNamed(Routes.home);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const LoadingSpinner(message: '云旅 App 启动中…'),
            const SizedBox(height: 40),
            Text('AI 优先 · 本地兜底',
                style: TextStyle(color: Colors.grey[600], fontSize: 13)),
          ],
        ),
      ),
    );
  }
}
