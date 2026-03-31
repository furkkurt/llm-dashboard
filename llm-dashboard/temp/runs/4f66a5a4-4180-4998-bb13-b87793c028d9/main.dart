import 'package:flutter/material.dart';

void main() {
  runApp(const NotepadApp());
}

class NotepadApp extends StatelessWidget {
  const NotepadApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Flutter Notepad',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.indigo),
        useMaterial3: true,
      ),
      home: const NotepadPage(),
    );
  }
}

class NotepadPage extends StatefulWidget {
  const NotepadPage({super.key});

  @override
  State<NotepadPage> createState() => _NotepadPageState();
}

class _NotepadPageState extends State<NotepadPage> {
  final TextEditingController _titleController = TextEditingController();
  final TextEditingController _contentController = TextEditingController();

  String _savedTitle = 'Untitled Note';
  String _savedContent = '';

  @override
  void dispose() {
    _titleController.dispose();
    _contentController.dispose();
    super.dispose();
  }

  void _saveNote() {
    setState(() {
      _savedTitle = _titleController.text.trim().isEmpty
          ? 'Untitled Note'
          : _titleController.text.trim();
      _savedContent = _contentController.text;
    });

    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Note saved')),
    );
  }

  void _clearNote() {
    _titleController.clear();
    _contentController.clear();

    setState(() {
      _savedTitle = 'Untitled Note';
      _savedContent = '';
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Basic Notepad'),
        centerTitle: true,
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextField(
              controller: _titleController,
              decoration: const InputDecoration(
                labelText: 'Note title',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 12),
            Expanded(
              child: TextField(
                controller: _contentController,
                maxLines: null,
                expands: true,
                textAlignVertical: TextAlignVertical.top,
                decoration: const InputDecoration(
                  labelText: 'Write your note here...',
                  alignLabelWithHint: true,
                  border: OutlineInputBorder(),
                ),
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: FilledButton.icon(
                    onPressed: _saveNote,
                    icon: const Icon(Icons.save),
                    label: const Text('Save'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _clearNote,
                    icon: const Icon(Icons.delete_outline),
                    label: const Text('Clear'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),
            const Divider(),
            const SizedBox(height: 8),
            Text(
              'Preview',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            Expanded(
              child: Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  border: Border.all(color: Colors.grey.shade400),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: SingleChildScrollView(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        _savedTitle,
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      const SizedBox(height: 8),
                      Text(
                        _savedContent.isEmpty
                            ? 'Your saved note will appear here.'
                            : _savedContent,
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}