import 'package:flutter/material.dart';

void main() {
  runApp(const NotepadApp());
}

class NotepadApp extends StatelessWidget {
  const NotepadApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Simple Notepad',
      theme: ThemeData(
        primarySwatch: Colors.amber,
        useMaterial3: true,
      ),
      home: const NotepadHome(),
    );
  }
}

class NotepadHome extends StatefulWidget {
  const NotepadHome({super.key});

  @override
  State<NotepadHome> createState() => _NotepadHomeState();
}

class _NotepadHomeState extends State<NotepadHome> {
  // This controller tracks everything you type
  final TextEditingController _noteController = TextEditingController();

  void _clearNote() {
    setState(() {
      _noteController.clear();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('My Notes'),
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
          controller: _noteController,
          maxLines: null, // Allows the note to grow vertically
          expands: true,  // Fills the screen
          keyboardType: TextInputType.multiline,
          textAlignVertical: TextAlignVertical.top,
          decoration: const InputDecoration(
            hintText: 'Start typing your thoughts...',
            border: InputBorder.none,
          ),
          style: const TextStyle(fontSize: 18.0, height: 1.5),
        ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () {
          // Logic for saving to a database could go here
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Note saved (locally)!')),
          );
        },
        child: const Icon(Icons.save),
      ),
    );
  }

  @override
  void dispose() {
    _noteController.dispose();
    super.dispose();
  }
}