import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:convert';

void main() {
  runApp(MyApp());
}

class MyApp extends StatelessWidget {
  @override
Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Basic Notepad',
      theme: ThemeData(
        primarySwatch: Colors.blue,
        visualDensity: VisualDensity.adaptivePlatformDensity,
      ),
      home: NoteListScreen(),
      debugShowCheckedModeBanner: false,
    );
  }
}

class Note {
  String id;
  String title;
  String content;
  DateTime createdAt;
  DateTime updatedAt;

  Note({
    required this.id,
    required this.title,
    required this.content,
    required this.createdAt,
    required this.updatedAt,
  });

  Map<String, dynamic> toJson() => {
    'id': id,
    'title': title,
    'content': content,
    'createdAt': createdAt.toIso8601String(),
    'updatedAt': updatedAt.toIso8601String(),
  };

  factory Note.fromJson(Map<String, dynamic> json) => Note(
    id: json['id'],
    title: json['title'],
    content: json['content'],
    createdAt: DateTime.parse(json['createdAt']),
    updatedAt: DateTime.parse(json['updatedAt']),
  );
}

class NoteListScreen extends StatefulWidget {
  @override
  _NoteListScreenState createState() => _NoteListScreenState();
}

class _NoteListScreenState extends State<NoteListScreen> {
  List<Note> _notes = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadNotes();
  }

  Future<void> _loadNotes() async {
    final prefs = await SharedPreferences.getInstance();
    final notesJson = prefs.getString('notes');
    
    if (notesJson != null) {
      List<dynamic> decodedList = json.decode(notesJson);
      setState(() {
        _notes = decodedList.map((item) => Note.fromJson(item)).toList();
        _notes.sort((a, b) => b.updatedAt.compareTo(a.updatedAt));
        _isLoading = false;
      });
    } else {
      setState(() {
        _isLoading = false;
      });
    }
  }

  Future<void> _saveNotes() async {
    final prefs = await SharedPreferences.getInstance();
    final notesJson = json.encode(_notes.map((note) => note.toJson()).toList());
    await prefs.setString('notes', notesJson);
  }

  void _addNote() {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => NoteEditorScreen(
          onSave: (title, content) {
            final newNote = Note(
              id: DateTime.now().millisecondsSinceEpoch.toString(),
              title: title,
              content: content,
              createdAt: DateTime.now(),
              updatedAt: DateTime.now(),
            );
            setState(() {
              _notes.insert(0, newNote);
            });
            _saveNotes();
          },
        ),
      ),
    );
  }

  void _editNote(Note note) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => NoteEditorScreen(
          note: note,
          onSave: (title, content) {
            setState(() {
              note.title = title;
              note.content = content;
              note.updatedAt = DateTime.now();
              _notes.sort((a, b) => b.updatedAt.compareTo(a.updatedAt));
            });
            _saveNotes();
          },
        ),
      ),
    );
  }

  void _deleteNote(Note note) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Delete Note'),
        content: Text('Are you sure you want to delete "${note.title}"?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text('Cancel'),
          ),
          TextButton(
            onPressed: () {
              setState(() {
                _notes.removeWhere((n) => n.id == note.id);
              });
              _saveNotes();
              Navigator.pop(context);
            },
            child: Text('Delete', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('My Notes'),
        centerTitle: true,
        elevation: 2,
      ),
      body: _isLoading
          ? Center(child: CircularProgressIndicator())
          : _notes.isEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(
                        Icons.note_add,
                        size: 80,
                        color: Colors.grey[400],
                      ),
                      SizedBox(height: 16),
                      Text(
                        'No notes yet',
                        style: TextStyle(
                          fontSize: 18,
                          color: Colors.grey[600],
                        ),
                      ),
                      SizedBox(height: 8),
                      Text(
                        'Tap the + button to create your first note',
                        style: TextStyle(
                          color: Colors.grey[500],
                        ),
                      ),
                    ],
                  ),
                )
              : ListView.builder(
                  itemCount: _notes.length,
                  itemBuilder: (context, index) {
                    final note = _notes[index];
                    return Dismissible(
                      key: Key(note.id),
                      background: Container(
                        color: Colors.red,
                        alignment: Alignment.centerRight,
                        padding: EdgeInsets.only(right: 20),
                        child: Icon(Icons.delete, color: Colors.white),
                      ),
                      direction: DismissDirection.endToStart,
                      onDismissed: (direction) {
                        _deleteNote(note);
                      },
                      child: Card(
                        margin: EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                        child: ListTile(
                          contentPadding: EdgeInsets.all(16),
                          title: Text(
                            note.title,
                            style: TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.bold,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          subtitle: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              SizedBox(height: 8),
                              Text(
                                note.content,
                                style: TextStyle(
                                  fontSize: 14,
                                  color: Colors.grey[600],
                                ),
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                              ),
                              SizedBox(height: 8),
                              Text(
                                _formatDate(note.updatedAt),
                                style: TextStyle(
                                  fontSize: 12,
                                  color: Colors.grey[500],
                                ),
                              ),
                            ],
                          ),
                          onTap: () => _editNote(note),
                          trailing: IconButton(
                            icon: Icon(Icons.delete_outline, color: Colors.grey),
                            onPressed: () => _deleteNote(note),
                          ),
                        ),
                      ),
                    );
                  },
                ),
      floatingActionButton: FloatingActionButton(
        onPressed: _addNote,
        child: Icon(Icons.add),
        tooltip: 'Add Note',
      ),
    );
  }

  String _formatDate(DateTime date) {
    final now = DateTime.now();
    final difference = now.difference(date);
    
    if (difference.inDays > 7) {
      return '${date.day}/${date.month}/${date.year}';
    } else if (difference.inDays > 0) {
      return '${difference.inDays} days ago';
    } else if (difference.inHours > 0) {
      return '${difference.inHours} hours ago';
    } else if (difference.inMinutes > 0) {
      return '${difference.inMinutes} minutes ago';
    } else {
      return 'Just now';
    }
  }
}

class NoteEditorScreen extends StatefulWidget {
  final Note? note;
  final Function(String title, String content) onSave;

  NoteEditorScreen({this.note, required this.onSave});

  @override
  _NoteEditorScreenState createState() => _NoteEditorScreenState();
}

class _NoteEditorScreenState extends State<NoteEditorScreen> {
  late TextEditingController _titleController;
  late TextEditingController _contentController;
  bool _isSaving = false;

  @override
  void initState() {
    super.initState();
    _titleController = TextEditingController(text: widget.note?.title ?? '');
    _contentController = TextEditingController(text: widget.note?.content ?? '');
  }

  @override
  void dispose() {
    _titleController.dispose();
    _contentController.dispose();
    super.dispose();
  }

  void _saveNote() {
    if (_titleController.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Please enter a title'),
          backgroundColor: Colors.orange,
        ),
      );
      return;
    }

    setState(() {
      _isSaving = true;
    });

    widget.onSave(
      _titleController.text.trim(),
      _contentController.text,
    );

    Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.note == null ? 'New Note' : 'Edit Note'),
        actions: [
          IconButton(
            icon: Icon(Icons.save),
            onPressed: _saveNote,
            tooltip: 'Save',
          ),
        ],
      ),
      body: Padding(
        padding: EdgeInsets.all(16),
        child: Column(
          children: [
            TextField(
              controller: _titleController,
              decoration: InputDecoration(
                hintText: 'Title',
                border: InputBorder.none,
                focusedBorder: UnderlineInputBorder(
                  borderSide: BorderSide(color: Colors.blue, width: 2),
                ),
                contentPadding: EdgeInsets.symmetric(vertical: 12),
              ),
              style: TextStyle(
                fontSize: 24,
                fontWeight: FontWeight.bold,
              ),
              maxLines: null,
            ),
            SizedBox(height: 16),
            Expanded(
              child: TextField(
                controller: _contentController,
                decoration: InputDecoration(
                  hintText: 'Start writing...',
                  border: InputBorder.none,
                  contentPadding: EdgeInsets.zero,
                ),
                style: TextStyle(
                  fontSize: 16,
                ),
                maxLines: null,
                expands: true,
                textAlignVertical: TextAlignVertical.top,
              ),
            ),
          ],
        ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _saveNote,
        child: Icon(Icons.check),
        tooltip: 'Save Note',
      ),
    );
  }
}