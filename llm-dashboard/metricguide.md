# Metric Implementation Guide for Cursor

This file provides specific hints for Cursor to modify the existing codebase to implement the cross-language metrics defined in metrics.md while preserving existing faithfulness metrics.

## Files to Modify

### 1. backend/models.py
**Task**: Extend the PaperScores model with new metric fields
**Location**: Find the PaperScores class definition
**Action**: Add these Optional fields (preserving existing fields, especially faithfulness-related ones):
```python
# Add after existing fields, before any methods
avg_cyclomatic_complexity: Optional[float] = None
loc: Optional[int] = None
comment_ratio: Optional[float] = None
halstead_volume: Optional[float] = None
halstead_difficulty: Optional[float] = None
maintainability_index: Optional[float] = None
avg_nesting_depth: Optional[float] = None
```
**Important**: Do NOT modify or remove any existing faithfulness_score_1_5, faithfulness_note, or related fields.

### 2. backend/metrics_util.py
**Task**: Add parser functions to extract metrics from tool outputs
**Location**: End of file or appropriate utility section
**Action**: Add these two functions:

```python
import xml.etree.ElementTree as ET
from statistics import mean
import json

def extract_cross_language_metrics_from_detekt(xml_path: str) -> dict:
    """Extract cross-language metrics from Detekt XML output"""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        metrics = {}
        
        # Cyclomatic complexity (avg)
        complexity_vals = [int(elem.text) for elem in root.findall(".//metric[@key='cyclomaticComplexity']")]
        metrics["avg_cyclomatic_complexity"] = mean(complexity_vals) if complexity_vals else 0.0
        
        # LOC and comments
        loc_elem = root.find(".//metric[@key='loc']")
        comment_elem = root.find(".//metric[@key='commentLines']")
        metrics["loc"] = int(loc_elem.text) if loc_elem is not None else 0
        metrics["comment_lines"] = int(comment_elem.text) if comment_elem is not None else 0
        metrics["comment_ratio"] = metrics["comment_lines"] / max(metrics["loc"], 1)
        
        # Halstead
        volume_elem = root.find(".//metric[@key='halsteadVolume']")
        difficulty_elem = root.find(".//metric[@key='halsteadDifficulty']")
        metrics["halstead_volume"] = float(volume_elem.text) if volume_elem is not None else 0.0
        metrics["halstead_difficulty"] = float(difficulty_elem.text) if difficulty_elem is not None else 0.0
        
        # Nesting depth
        depth_elem = root.find(".//metric[@key='nestedBlockDepth']")
        metrics["avg_nesting_depth"] = float(depth_elem.text) if depth_elem is not None else 0.0
        
        return metrics
    except Exception as e:
        # Return empty dict on error to not break pipeline
        return {}

def extract_cross_language_metrics_from_dart(json_path: str) -> dict:
    """Extract cross-language metrics from Dart analyzer output"""
    try:
        with open(json_path) as f:
            data = json.load(f)
        metrics = {}
        
        # Adapt this based on actual Dart analyzer output format
        # Example structure - adjust to match your actual output:
        if isinstance(data, dict):
            # Cyclomatic complexity
            metrics["avg_cyclomatic_complexity"] = data.get("cyclomatic_complexity", 0.0)
            
            # LOC and comments
            metrics["loc"] = data.get("lines_of_code", 0)
            metrics["comment_lines"] = data.get("comment_lines", 0)
            metrics["comment_ratio"] = metrics["comment_lines"] / max(metrics["loc"], 1)
            
            # Halstead
            metrics["halstead_volume"] = data.get("halstead_volume", 0.0)
            metrics["halstead_difficulty"] = data.get("halstead_difficulty", 0.0)
            
            # Nesting depth
            metrics["avg_nesting_depth"] = data.get("nesting_depth", 0.0)
        
        return metrics
    except Exception as e:
        # Return empty dict on error to not break pipeline
        return {}
```

### 3. runners/run_detekt.py
**Task**: Call the Detekt parser and merge results
**Location**: After Detekt runs and produces output file, before saving results
**Action**: 
1. Import the parser function at top: `from backend.metrics_util import extract_cross_language_metrics_from_detekt`
2. After Detekt execution but before calling save_analysis_result:
```python
# After Detekt runs and output file is available
detekt_metrics = extract_cross_language_metrics_from_detekt(detekt_output_path)
# Merge with existing base_metrics
final_metrics = {**base_metrics, **detekt_metrics}
# Use final_metrics in save_analysis_result call
```

### 4. runners/run_dart_analyze.py
**Task**: Call the Dart parser and merge results
**Location**: After Dart analyzer runs and produces output file, before saving results
**Action**:
1. Import the parser function at top: `from backend.metrics_util import extract_cross_language_metrics_from_dart`
2. After Dart analyzer execution but before calling save_analysis_result:
```python
# After Dart analyzer runs and output file is available
dart_metrics = extract_cross_language_metrics_from_dart(dart_output_path)
# Merge with existing base_metrics
final_metrics = {**base_metrics, **dart_metrics}
# Use final_metrics in save_analysis_result call
```

## Critical Preservation Rules

### DO NOT MODIFY:
- Any existing faithfulness-related fields in PaperScores model
- Any existing faithfulness evaluation logic in backend/ or frontend/
- The save_analysis_result function signature or core logic
- Existing metric fields in PaperScores (like those related to paper_scores)
- The frontend/app.py faithfulness UI components (sliders, auto-commentary checkbox, etc.)

### SAFE TO MODIFY:
- Adding new fields to PaperScores model
- Adding new parser functions in metrics_util.py
- Calling parsers and merging results in the runner scripts
- Adding new imports where needed

## Testing Approach

After making changes:
1. Run `./start.sh` to verify both services start correctly
2. Submit a test analysis through the UI
3. Check that new metrics appear in stored results (via /results endpoint or history tab)
4. Verify faithfulness metrics still work exactly as before
5. Ensure no regression in existing functionality

## Verification Points

Cursor should verify that:
1. PaperScores model accepts the new fields without breaking existing code
2. The parsers return appropriate dictionary structures
3. Metrics are properly merged and saved with analysis results
4. Historical results can still be loaded and displayed
5. Winner computation and history filtering still work with new fields present
6. Faithfulness sliders, auto-commentary, and patching functionality remain intact

This approach ensures minimal, focused changes that add the requested metrics while protecting the existing faithfulness evaluation system.