import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  runApp(const NotepadApp());
}

class NotepadApp extends StatelessWidget {
  const NotepadApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Quick Note',
      theme: ThemeData(
        primarySwatch: Colors.amber,
        useMaterial3: true,
      ),
      home: const NoteScreen(),
    );
  }
}

class NoteScreen extends StatefulWidget {
  const NoteScreen({super.key});

  @override
  State<NoteScreen> createState() => _NoteScreenState();
}

class _NoteScreenState extends State<NoteScreen> {
  final TextEditingController _controller = TextEditingController();

  @override
  void initState() {
    super.initState();
    _loadNote();
  }

  // Load the saved note from disk
  Future<void> _loadNote() async {
    final prefs = await SharedPreferences.getInstance();
    setState(() {
      _controller.text = prefs.getString('saved_note') ?? "";
    });
  }

  // Save the note to disk
  Future<void> _saveNote(String text) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('saved_note', text);
  }

  void _clearNote() {
    _controller.clear();
    _saveNote("");
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('My Notes'),
        backgroundColor: Colors.amber[100],
        actions: [
          IconButton(
            icon: const Icon(Icons.delete_outline),
            onPressed: _clearNote,
            tooltip: 'Clear Note',
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: TextField(
          controller: _controller,
          maxLines: null, // Allows the note to expand vertically
          expands: true, // Fills the screen
          style: const TextStyle(fontSize: 18, height: 1.5),
          decoration: const InputDecoration(
            hintText: 'Start typing your thoughts...',
            border: InputBorder.none,
          ),
          onChanged: (value) {
            _saveNote(value); // Auto-save on every keystroke
          },
        ),
      ),
    );
  }
}