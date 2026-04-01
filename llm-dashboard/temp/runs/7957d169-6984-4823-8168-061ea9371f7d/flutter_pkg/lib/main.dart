import 'package:flutter/material.dart';

void main() => runApp(const MaterialApp(home: NotepadPage()));

class NotepadPage extends StatefulWidget {
  const NotepadPage({super.key});

  @override
  State<NotepadPage> createState() => _NotepadPageState();
}

class _NotepadPageState extends State<NotepadPage> {
  final _controller = TextEditingController();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Notepad'),
        actions: [
          IconButton(
            icon: const Icon(Icons.delete_outline),
            tooltip: 'Clear',
            onPressed: () => setState(() => _controller.clear()),
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: TextField(
          controller: _controller,
          maxLines: null,
          expands: true,
          autofocus: true,
          decoration: const InputDecoration(
            hintText: 'Start typing...',
            border: InputBorder.none,
          ),
          style: const TextStyle(fontSize: 16, height: 1.6),
        ),
      ),
    );
  }
}