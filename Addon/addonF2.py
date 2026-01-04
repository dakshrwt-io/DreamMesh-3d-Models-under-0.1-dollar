# -------------------------------------------------------------------
# AI 3D Generator Pro — Enhanced Version with Improved Execution
# Requires Blender ≥ 3.6, Python ≥ 3.10
# -------------------------------------------------------------------

bl_info = {
    "name": "MODEL GENERATOR ",
    "author": "Enhanced by AI Assistant",
    "version": (1, 0, 1),
    "blender": (3, 6, 0),
    "location": "3D View > Sidebar > AI Tools",
    "description": "Generate 3D models from AI prompts with n8n webhook integration and scene analysis - Enhanced execution with unified context",
    "category": "3D View",
    "doc_url": "https://github.com/yourusername/ai-3d-generator",
    "support": "COMMUNITY",
}

import bpy
import json
import queue
import threading
import time
import requests
import traceback
import math
import random
import re
import bmesh
import mathutils
from mathutils import Vector, Euler, Matrix, Quaternion, noise
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from bpy.app.handlers import persistent
from bpy.props import StringProperty, IntProperty, BoolProperty, EnumProperty
from bpy.types import PropertyGroup, AddonPreferences, Panel, Operator

# -------------------------------------------------------------------
# Global State Management with Thread Safety
# -------------------------------------------------------------------

JOB_QUEUE = queue.Queue()
RESULT_QUEUE = queue.Queue()
CODE_EXECUTION_QUEUE = queue.Queue()
HTTPD = None
SERVER_THREAD = None

# -------------------------------------------------------------------
# Error Categorization & Fix Suggestions for n8n
# -------------------------------------------------------------------

def categorize_blender_error(error_type: str, error_message: str, traceback: str) -> str:
    """
    Categorize Blender errors for smarter n8n retry logic.
    Returns a category string that n8n can use to decide how to handle the error.
    """
    error_lower = error_message.lower()
    traceback_lower = traceback.lower()
    
    # Syntax errors - code structure issues
    if error_type in ['SyntaxError', 'IndentationError', 'TabError']:
        return 'SYNTAX_ERROR'
    
    # Name/Attribute errors - wrong API usage
    if error_type == 'NameError':
        return 'UNDEFINED_NAME'
    if error_type == 'AttributeError':
        if 'has no attribute' in error_lower:
            return 'INVALID_ATTRIBUTE'
        return 'ATTRIBUTE_ERROR'
    
    # Type errors - wrong parameter types
    if error_type == 'TypeError':
        if 'argument' in error_lower or 'parameter' in error_lower:
            return 'WRONG_ARGUMENT_TYPE'
        if 'not callable' in error_lower:
            return 'NOT_CALLABLE'
        return 'TYPE_ERROR'
    
    # Value errors - wrong values
    if error_type == 'ValueError':
        return 'INVALID_VALUE'
    
    # Key/Index errors - wrong access
    if error_type in ['KeyError', 'IndexError']:
        return 'ACCESS_ERROR'
    
    # Blender-specific context errors
    if 'context' in error_lower or 'poll' in error_lower:
        return 'CONTEXT_ERROR'
    
    # BMesh specific errors
    if 'bmesh' in traceback_lower:
        if 'freed' in error_lower or 'invalid' in error_lower:
            return 'BMESH_FREED_ERROR'
        return 'BMESH_ERROR'
    
    # Operator errors
    if 'bpy.ops' in traceback_lower or 'operator' in error_lower:
        return 'OPERATOR_ERROR'
    
    # Memory/Resource errors
    if error_type in ['MemoryError', 'RecursionError']:
        return 'RESOURCE_ERROR'
    
    # Import errors
    if error_type in ['ImportError', 'ModuleNotFoundError']:
        return 'IMPORT_ERROR'
    
    # Runtime errors
    if error_type == 'RuntimeError':
        if 'context' in error_lower:
            return 'RUNTIME_CONTEXT_ERROR'
        return 'RUNTIME_ERROR'
    
    # Zero division
    if error_type == 'ZeroDivisionError':
        return 'MATH_ERROR'
    
    return 'UNKNOWN_ERROR'


def get_fix_suggestions(error_category: str, error_type: str, error_message: str) -> list:
    """
    Provide actionable fix suggestions based on error category.
    These suggestions help the LLM generate corrected code.
    """
    suggestions = {
        'SYNTAX_ERROR': [
            'Check for missing colons, parentheses, or brackets',
            'Verify proper indentation (use 4 spaces)',
            'Ensure all strings are properly quoted',
            'Check for invalid Python syntax'
        ],
        'UNDEFINED_NAME': [
            'Ensure all variables are defined before use',
            'Check for typos in variable/function names',
            'Import required modules (bpy, bmesh, mathutils)',
            'Define functions before calling them'
        ],
        'INVALID_ATTRIBUTE': [
            'Check Blender 4.4 API documentation for correct attribute names',
            'Use bpy.data.objects.get() instead of direct access',
            'Verify object type before accessing type-specific attributes',
            'Common fixes: .location not .position, .scale not .size'
        ],
        'ATTRIBUTE_ERROR': [
            'Verify the object type has the attribute you are accessing',
            'Check if the object is None before accessing attributes',
            'Use hasattr() to check attribute existence'
        ],
        'WRONG_ARGUMENT_TYPE': [
            'Check function signature for expected parameter types',
            'Convert values to correct types (int, float, tuple, list)',
            'Use Vector() for vector parameters, tuple for colors'
        ],
        'TYPE_ERROR': [
            'Verify argument types match function requirements',
            'Check if you are calling a method on the correct object type',
            'Ensure iterables are actual lists/tuples not single values'
        ],
        'INVALID_VALUE': [
            'Check value ranges (e.g., positive values for sizes)',
            'Verify enum values match Blender API expectations',
            'Ensure coordinates are valid numbers'
        ],
        'ACCESS_ERROR': [
            'Use .get() method with default value for safe access',
            'Check collection/list length before indexing',
            'Verify key exists in dictionary before access'
        ],
        'CONTEXT_ERROR': [
            'Ensure correct mode (OBJECT/EDIT) for the operation',
            'Use bpy.context.view_layer.objects.active for active object',
            'Some operators require specific area types or selections',
            'Use override context for operators when needed'
        ],
        'BMESH_FREED_ERROR': [
            'Do not use bmesh after calling bm.free()',
            'Create new bmesh if you need to use it again',
            'Call bm.to_mesh() before bm.free()'
        ],
        'BMESH_ERROR': [
            'Ensure mesh is in correct mode for bmesh operations',
            'Use bmesh.from_edit_mesh() in edit mode',
            'Call bm.normal_update() after geometry changes',
            'Always call bm.free() when done with bmesh'
        ],
        'OPERATOR_ERROR': [
            'AVOID using bpy.ops - use bmesh/direct data manipulation instead',
            'If operator needed, ensure correct context and mode',
            'Check operator poll() conditions are met'
        ],
        'RESOURCE_ERROR': [
            'Reduce geometry complexity',
            'Free resources (bmesh, temporary data) when done',
            'Avoid infinite loops or deep recursion'
        ],
        'IMPORT_ERROR': [
            'Standard imports: bpy, bmesh, mathutils, math, random',
            'Check module name spelling',
            'Some modules may not be available in Blender Python'
        ],
        'RUNTIME_CONTEXT_ERROR': [
            'Operation requires specific Blender context',
            'Ensure you are not in wrong mode (EDIT vs OBJECT)',
            'Some operations need active/selected objects'
        ],
        'RUNTIME_ERROR': [
            'Check for invalid operations on current state',
            'Verify object/data validity before operations',
            'Review the specific error message for clues'
        ],
        'MATH_ERROR': [
            'Add checks for zero values before division',
            'Use safe division: x / max(y, 0.0001)',
            'Validate mathematical inputs'
        ],
        'UNKNOWN_ERROR': [
            'Review the full traceback for specific error location',
            'Check Blender 4.4 API for any deprecated functions',
            'Ensure all objects exist before manipulation',
            'Add try/except blocks around risky operations'
        ]
    }
    
    return suggestions.get(error_category, suggestions['UNKNOWN_ERROR'])


# -------------------------------------------------------------------
# Scene Analysis Functions
# -------------------------------------------------------------------

def get_detailed_scene_info():
    """Extract comprehensive scene information"""
    scene = bpy.context.scene
    scene_info = {
        "timestamp": time.time(),
        "scene_name": scene.name,
        "frame_current": scene.frame_current,
        "frame_start": scene.frame_start,
        "frame_end": scene.frame_end,
        "objects": [],
        "materials": [],
        "cameras": [],
        "lights": [],
        "collections": [],
        "world_settings": {},
        "render_settings": {}
    }

    # Get all objects with detailed info
    for obj in scene.objects:
        obj_info = {
            "name": obj.name,
            "type": obj.type,
            "location": list(obj.location),
            "rotation": list(obj.rotation_euler),
            "scale": list(obj.scale),
            "visible": obj.visible_get(),
            "hide_viewport": obj.hide_viewport,
            "hide_render": obj.hide_render,
        }

        if obj.type == 'MESH':
            if obj.data:
                obj_info.update({
                    "vertices": len(obj.data.vertices),
                    "edges": len(obj.data.edges),
                    "faces": len(obj.data.polygons),
                    "materials": [mat.name for mat in obj.data.materials if mat]
                })
            scene_info["objects"].append(obj_info)
        elif obj.type == 'CAMERA':
            if obj.data:
                obj_info.update({
                    "lens": obj.data.lens,
                    "sensor_width": obj.data.sensor_width,
                    "clip_start": obj.data.clip_start,
                    "clip_end": obj.data.clip_end,
                    "type": obj.data.type
                })
            scene_info["cameras"].append(obj_info)
        elif obj.type == 'LIGHT':
            if obj.data:
                obj_info.update({
                    "light_type": obj.data.type,
                    "energy": obj.data.energy,
                    "color": list(obj.data.color),
                    "use_shadow": obj.data.use_shadow
                })
            scene_info["lights"].append(obj_info)

    # Get materials info
    for mat in bpy.data.materials:
        if mat.users > 0:
            mat_info = {
                "name": mat.name,
                "use_nodes": mat.use_nodes,
                "users": mat.users
            }
            if mat.use_nodes and mat.node_tree:
                principled = None
                for node in mat.node_tree.nodes:
                    if node.type == 'BSDF_PRINCIPLED':
                        principled = node
                        break
                if principled:
                    mat_info["base_color"] = list(principled.inputs['Base Color'].default_value)
                    mat_info["metallic"] = principled.inputs['Metallic'].default_value
                    mat_info["roughness"] = principled.inputs['Roughness'].default_value
            scene_info["materials"].append(mat_info)

    # Get collections info
    for collection in bpy.data.collections:
        if collection.name in scene.collection.children or collection == scene.collection:
            coll_info = {
                "name": collection.name,
                "objects": [obj.name for obj in collection.objects],
                "hide_viewport": collection.hide_viewport,
                "hide_render": collection.hide_render
            }
            scene_info["collections"].append(coll_info)

    # World settings
    if scene.world:
        scene_info["world_settings"] = {
            "name": scene.world.name,
            "use_nodes": scene.world.use_nodes
        }
        if scene.world.use_nodes and scene.world.node_tree:
            for node in scene.world.node_tree.nodes:
                if node.type == 'BACKGROUND':
                    scene_info["world_settings"]["background_color"] = list(node.inputs['Color'].default_value)
                    break
                elif node.type == 'TEX_ENVIRONMENT':
                    if node.image:
                        scene_info["world_settings"]["hdri_name"] = node.image.name
                    break

    # Render settings
    scene_info["render_settings"] = {
        "engine": scene.render.engine,
        "resolution_x": scene.render.resolution_x,
        "resolution_y": scene.render.resolution_y,
        "resolution_percentage": scene.render.resolution_percentage,
        "frame_map_old": scene.render.frame_map_old,
        "frame_map_new": scene.render.frame_map_new,
        "fps": scene.render.fps
    }

    return scene_info

def format_scene_summary(scene_info):
    """Create a human-readable summary of the scene"""
    summary = []
    summary.append(f"Scene: {scene_info['scene_name']}")
    summary.append(f"Objects: {len(scene_info['objects'])} meshes, {len(scene_info['cameras'])} cameras, {len(scene_info['lights'])} lights")
    if scene_info['objects']:
        mesh_names = [obj['name'] for obj in scene_info['objects']]
        summary.append(f"Mesh objects: {', '.join(mesh_names[:5])}")
        if len(mesh_names) > 5:
            summary.append(f"... and {len(mesh_names) - 5} more")
    if scene_info['materials']:
        mat_names = [mat['name'] for mat in scene_info['materials']]
        summary.append(f"Materials: {', '.join(mat_names[:3])}")
        if len(mat_names) > 3:
            summary.append(f"... and {len(mat_names) - 3} more")
    summary.append(f"Render engine: {scene_info['render_settings']['engine']}")
    summary.append(f"Resolution: {scene_info['render_settings']['resolution_x']}x{scene_info['render_settings']['resolution_y']}")
    return "\n".join(summary)

# -------------------------------------------------------------------
# Scene Properties
# -------------------------------------------------------------------

class AIGeneratorProperties(PropertyGroup):
    ai_prompt: StringProperty(
        name="AI Prompt",
        description="Describe the 3D model you want to generate",
        default="A simple cube with rounded edges",
        maxlen=10000
    )

    generation_status: StringProperty(
        name="Status",
        default="Ready"
    )

    auto_material: BoolProperty(
        name="Auto Material",
        description="Automatically apply materials to generated objects",
        default=True
    )

    complexity_level: EnumProperty(
        name="Complexity",
        description="Model generation complexity",
        items=[
            ('SIMPLE', 'Simple', 'Basic geometric shapes'),
            ('MEDIUM', 'Medium', 'Moderate detail level'),
            ('COMPLEX', 'Complex', 'High detail level'),
        ],
        default='MEDIUM'
    )

    include_scene_context: BoolProperty(
        name="Include Scene Context",
        description="Include current scene details when sending to n8n",
        default=True
    )

    safe_mode: BoolProperty(
        name="Safe Mode",
        description="Enable additional safety checks for code execution",
        default=True
    )

# -------------------------------------------------------------------
# Add-on Preferences
# -------------------------------------------------------------------

class AIGeneratorPrefs(AddonPreferences):
    bl_idname = __name__

    listen_port: IntProperty(
        name="Webhook Port",
        description="Port for incoming n8n webhooks",
        default=8765,
        min=1024,
        max=65535,
    )

    post_back_url: StringProperty(
        name="Result Webhook URL",
        description="URL to send generation results back to n8n",
        default="http://localhost:5678/webhook-test/result",
    )

    n8n_workflow_url: StringProperty(
        name="n8n Workflow URL",
        description="URL to send prompts to n8n workflow for processing",
        default="http://localhost:5678/webhook-test/process",
    )

    enable_logging: BoolProperty(
        name="Enable Detailed Logging",
        description="Print detailed logs to console",
        default=True
    )

    auto_start_server: BoolProperty(
        name="Auto-start Server",
        description="Automatically start webhook server on add-on enable",
        default=False
    )

    max_execution_time: IntProperty(
        name="Max Execution Time (seconds)",
        description="Maximum time allowed for code execution",
        default=30,
        min=5,
        max=300
    )

    def draw(self, context):
        layout = self.layout
        # Server Settings
        box = layout.box()
        box.label(text="Server Configuration:", icon='PREFERENCES')
        box.prop(self, "listen_port")
        box.prop(self, "post_back_url")
        box.prop(self, "n8n_workflow_url")
        box.prop(self, "auto_start_server")
        # Debug Settings
        box = layout.box()
        box.label(text="Debug Options:", icon='CONSOLE')
        box.prop(self, "enable_logging")
        box.prop(self, "max_execution_time")
        # Server Status
        box = layout.box()
        box.label(text="Server Status:", icon='INFO')
        status = "Running" if HTTPD else "Stopped"
        color = 'CHECKMARK' if HTTPD else 'X'
        box.label(text=f"Webhook Server: {status}", icon=color)

# -------------------------------------------------------------------
# Enhanced Safe Code Execution Functions - FIXED VERSION
# -------------------------------------------------------------------

def execute_code_on_main_thread(code, scene_info):
    """Queue code for execution on Blender's main thread"""
    execution_data = {
        'code': code,
        'scene_info': scene_info,
        'timestamp': time.time()
    }
    CODE_EXECUTION_QUEUE.put(execution_data)
    log_message("Code queued for main thread execution")


# Global result container for synchronous execution
_SYNC_EXECUTION_RESULT = {"result": None, "completed": False}


def execute_code_synchronously(code, scene_info):
    """
    Execute code synchronously and wait for result.
    Blocks the HTTP response until execution completes.
    Returns the full execution result dict for n8n.
    """
    global _SYNC_EXECUTION_RESULT
    
    # Reset result container
    _SYNC_EXECUTION_RESULT = {"result": None, "completed": False}
    
    def execute_and_store():
        """Execute code on main thread and store result"""
        global _SYNC_EXECUTION_RESULT
        try:
            log_message("⚡ Executing code in main thread context...")
            result = safe_execute_code_sync(code, scene_info)
            _SYNC_EXECUTION_RESULT["result"] = result
            _SYNC_EXECUTION_RESULT["completed"] = True
        except Exception as e:
            _SYNC_EXECUTION_RESULT["result"] = {
                "code_executed": False,
                "execution_status": "failed",
                "error_category": categorize_blender_error(type(e).__name__, str(e), traceback.format_exc()),
                "error_type": type(e).__name__,
                "error_message": str(e),
                "error_traceback": traceback.format_exc(),
                "original_code": code,
                "fix_suggestions": get_fix_suggestions(
                    categorize_blender_error(type(e).__name__, str(e), traceback.format_exc()),
                    type(e).__name__,
                    str(e)
                )
            }
            _SYNC_EXECUTION_RESULT["completed"] = True
        return None  # Unregister timer
    
    # Queue execution on main thread
    bpy.app.timers.register(execute_and_store, first_interval=0.001)
    
    # Wait for execution to complete (with timeout)
    timeout = 120  # 120 seconds max for complex geometry
    start_time = time.time()
    
    while not _SYNC_EXECUTION_RESULT["completed"]:
        if time.time() - start_time > timeout:
            return {
                "code_executed": False,
                "execution_status": "timeout",
                "error_category": "TIMEOUT_ERROR",
                "error_type": "TimeoutError",
                "error_message": f"Code execution exceeded {timeout} seconds",
                "original_code": code,
                "fix_suggestions": [
                    "Reduce geometry complexity",
                    "Optimize loops and operations",
                    "Break into smaller operations"
                ]
            }
        time.sleep(0.05)  # Check every 50ms
    
    return _SYNC_EXECUTION_RESULT["result"]


def safe_execute_code_sync(code, scene_info):
    """
    Execute code safely and return full result dict (for synchronous webhook response).
    Does NOT send to n8n - returns the result instead.
    """
    try:
        if not bpy.context.scene:
            raise Exception("No active scene available")
        if not bpy.context.view_layer:
            raise Exception("No active view layer")

        objects_before = set(bpy.context.scene.objects.keys())

        # Ensure we're in object mode
        if bpy.context.active_object and bpy.context.mode != 'OBJECT':
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
            except:
                pass

        # Enhanced execution context
        execution_context = {
            '__builtins__': __builtins__,
            'bpy': bpy,
            'bmesh': bmesh,
            'math': math,
            'random': random,
            'time': time,
            'radians': math.radians,
            'degrees': math.degrees,
            'sin': math.sin,
            'cos': math.cos,
            'tan': math.tan,
            'asin': math.asin,
            'acos': math.acos,
            'atan': math.atan,
            'atan2': math.atan2,
            'sqrt': math.sqrt,
            'pow': math.pow,
            'log': math.log,
            'log10': math.log10,
            'exp': math.exp,
            'floor': math.floor,
            'ceil': math.ceil,
            'fabs': math.fabs,
            'abs': abs,
            'min': min,
            'max': max,
            'round': round,
            'sum': sum,
            'len': len,
            'range': range,
            'enumerate': enumerate,
            'zip': zip,
            'pi': math.pi,
            'e': math.e,
            'tau': math.tau if hasattr(math, 'tau') else math.pi * 2,
            'mathutils': mathutils,
            'Vector': Vector,
            'Euler': Euler,
            'Matrix': Matrix,
            'Quaternion': Quaternion,
            'noise': noise,
            'log_message': log_message,
            'print': print,
            'list': list,
            'dict': dict,
            'tuple': tuple,
            'set': set,
            'context': bpy.context,
            'scene': bpy.context.scene,
            'view_layer': bpy.context.view_layer,
            'scene_info': scene_info,
            'current_scene': bpy.context.scene,
            'objects': bpy.data.objects,
            'collections': bpy.data.collections,
            'materials': bpy.data.materials,
            'meshes': bpy.data.meshes,
            'curves': bpy.data.curves,
            'lights': bpy.data.lights,
            'cameras': bpy.data.cameras,
            'images': bpy.data.images,
            'textures': bpy.data.textures,
        }

        log_message(f"Starting synchronous code execution (length: {len(code)} characters)...")
        
        start_time = time.time()
        exec(code, execution_context, execution_context)
        execution_time = time.time() - start_time

        # Update the view layer and redraw
        bpy.context.view_layer.update()

        # Force viewport refresh
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

        # Calculate what was created
        objects_after = set(bpy.context.scene.objects.keys())
        new_objects = objects_after - objects_before

        # Get updated scene information
        updated_scene_info = get_detailed_scene_info()

        # Build success response
        result = {
            'code_executed': True,
            'execution_status': 'success',
            'status': 'code_executed_successfully',
            'message': f'Code executed successfully in {execution_time:.2f}s. Created {len(new_objects)} new objects.',
            'new_objects': list(new_objects),
            'objects_created': len(new_objects),
            'execution_time_seconds': round(execution_time, 3),
            'scene_after': updated_scene_info,
            'scene_summary': format_scene_summary(updated_scene_info),
            'code_length': len(code),
            'timestamp': time.time(),
            'blender_version': bpy.app.version_string,
            'error': None,
            'error_type': None,
            'error_message': None,
            'error_line': None,
        }

        log_message(f"✅ Code executed successfully in {execution_time:.2f}s. Created objects: {new_objects}")
        bpy.context.scene.ai_generator_props.generation_status = f"Success: {len(new_objects)} objects created"
        return result

    except Exception as e:
        full_traceback = traceback.format_exc()
        error_type = type(e).__name__
        error_message = str(e)
        error_category = categorize_blender_error(error_type, error_message, full_traceback)
        
        # Extract line number
        error_line = None
        problematic_code_section = None
        try:
            tb_lines = full_traceback.split('\n')
            for line in tb_lines:
                if 'line' in line.lower() and ('<string>' in line or 'exec' in line):
                    line_match = re.search(r'line (\d+)', line)
                    if line_match:
                        error_line = int(line_match.group(1))
                        code_lines = code.split('\n')
                        if error_line and error_line <= len(code_lines):
                            start = max(0, error_line - 3)
                            end = min(len(code_lines), error_line + 2)
                            problematic_code_section = '\n'.join(
                                [f"{j+1}: {code_lines[j]}" for j in range(start, end)]
                            )
                        break
        except Exception:
            pass

        log_message(f"❌ Code execution failed: {error_type}: {error_message}")
        log_message(f"Error category: {error_category}")
        
        bpy.context.scene.ai_generator_props.generation_status = f"Failed: {error_message[:50]}..."

        # Build error response
        return {
            'code_executed': False,
            'execution_status': 'failed',
            'error_category': error_category,
            'error_type': error_type,
            'error_message': error_message,
            'error_line': error_line,
            'error_traceback': full_traceback,
            'problematic_code_section': problematic_code_section,
            'original_code': code,
            'code_length': len(code),
            'fix_suggestions': get_fix_suggestions(error_category, error_type, error_message),
            'blender_context': {
                'scene_available': bpy.context.scene is not None,
                'view_layer_available': bpy.context.view_layer is not None,
                'active_object': bpy.context.active_object.name if bpy.context.active_object else None,
                'mode': getattr(bpy.context, 'mode', 'UNKNOWN'),
            },
            'timestamp': time.time(),
            'blender_version': bpy.app.version_string,
            'status': 'code_execution_failed',
            'message': f'{error_category}: {error_type} - {error_message}'
        }


def safe_execute_code(code, scene_info):
    """Execute code safely with enhanced context and error handling - FIXED FOR UNIFIED CONTEXT"""
    try:
        if not bpy.context.scene:
            raise Exception("No active scene available")
        if not bpy.context.view_layer:
            raise Exception("No active view layer")

        objects_before = set(bpy.context.scene.objects.keys())

        # Ensure we're in object mode
        if bpy.context.active_object and bpy.context.mode != 'OBJECT':
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
            except:
                pass

        # Enhanced execution context - UNIFIED FOR BOTH GLOBALS AND LOCALS
        execution_context = {
            '__builtins__': __builtins__,

            # Core Blender APIs
            'bpy': bpy,
            'bmesh': bmesh,

            # Math libraries and functions
            'math': math,
            'random': random,
            'time': time,

            # Common math functions directly accessible
            'radians': math.radians,
            'degrees': math.degrees,
            'sin': math.sin,
            'cos': math.cos,
            'tan': math.tan,
            'asin': math.asin,
            'acos': math.acos,
            'atan': math.atan,
            'atan2': math.atan2,
            'sqrt': math.sqrt,
            'pow': math.pow,
            'log': math.log,
            'log10': math.log10,
            'exp': math.exp,
            'floor': math.floor,
            'ceil': math.ceil,
            'fabs': math.fabs,
            'abs': abs,
            'min': min,
            'max': max,
            'round': round,
            'sum': sum,
            'len': len,
            'range': range,
            'enumerate': enumerate,
            'zip': zip,
            'pi': math.pi,
            'e': math.e,
            'tau': math.tau if hasattr(math, 'tau') else math.pi * 2,

            # Mathutils - comprehensive vector/matrix math
            'mathutils': mathutils,
            'Vector': Vector,
            'Euler': Euler,
            'Matrix': Matrix,
            'Quaternion': Quaternion,
            'noise': noise,

            # Utility functions
            'log_message': log_message,
            'print': print,  # Allow printing for debugging

            # Collection types
            'list': list,
            'dict': dict,
            'tuple': tuple,
            'set': set,

            # Blender context - added to unified context
            'context': bpy.context,
            'scene': bpy.context.scene,
            'view_layer': bpy.context.view_layer,
            'scene_info': scene_info,
            'current_scene': bpy.context.scene,
            'objects': bpy.data.objects,
            'collections': bpy.data.collections,
            'materials': bpy.data.materials,
            'meshes': bpy.data.meshes,
            'curves': bpy.data.curves,
            'lights': bpy.data.lights,
            'cameras': bpy.data.cameras,
            'images': bpy.data.images,
            'textures': bpy.data.textures,
        }

        # Log code execution start
        log_message(f"Starting unified context code execution (length: {len(code)} characters)...")
        
        # CRITICAL FIX: Execute with same context for both globals and locals
        # This ensures function definitions are available for subsequent function calls
        start_time = time.time()
        exec(code, execution_context, execution_context)
        execution_time = time.time() - start_time

        # Update the view layer and redraw
        bpy.context.view_layer.update()

        # Force viewport refresh
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

        # Calculate what was created
        objects_after = set(bpy.context.scene.objects.keys())
        new_objects = objects_after - objects_before

        # Get updated scene information
        updated_scene_info = get_detailed_scene_info()

        # Build comprehensive result
        result = {
            'status': 'code_executed_successfully',
            'message': f'Code executed successfully in {execution_time:.2f}s. Created {len(new_objects)} new objects.',
            # Primary execution status - USE THIS IN N8N
            'code_executed': True,
            'execution_status': 'success',
            
            # Execution details
            'new_objects': list(new_objects),
            'objects_created': len(new_objects),
            'execution_time_seconds': round(execution_time, 3),
            
            # Scene state
            'scene_before': scene_info,
            'scene_after': updated_scene_info,
            'scene_summary': format_scene_summary(updated_scene_info),
            
            # Metadata
            'code_length': len(code),
            'timestamp': time.time(),
            'blender_version': bpy.app.version_string,
            
            # Error info (empty on success)
            'error': None,
            'error_type': None,
            'error_message': None,
            'error_line': None,
        }

        log_message(f"Code executed successfully in {execution_time:.2f}s. Created objects: {new_objects}")
        # NOTE: Don't send to n8n here - synchronous webhook handles response
        # send_result_to_n8n(result)
        bpy.context.scene.ai_generator_props.generation_status = f"Success: {len(new_objects)} objects created in {execution_time:.2f}s"
        return True

    except Exception as e:
        # Enhanced error capture with comprehensive context for n8n retry logic
        full_traceback = traceback.format_exc()
        error_type = type(e).__name__
        error_message = str(e)
        
        # Categorize error for smarter n8n handling
        error_category = categorize_blender_error(error_type, error_message, full_traceback)
        
        # Extract line number from traceback
        error_line = None
        problematic_code_section = None
        try:
            tb_lines = full_traceback.split('\n')
            for i, line in enumerate(tb_lines):
                if 'line' in line.lower() and ('<string>' in line or 'exec' in line):
                    line_match = re.search(r'line (\d+)', line)
                    if line_match:
                        error_line = int(line_match.group(1))
                        # Extract the problematic code section
                        code_lines = code.split('\n')
                        if error_line and error_line <= len(code_lines):
                            start = max(0, error_line - 3)
                            end = min(len(code_lines), error_line + 2)
                            problematic_code_section = '\n'.join(
                                [f"{j+1}: {code_lines[j]}" for j in range(start, end)]
                            )
                        break
        except Exception:
            pass

        log_message(f"Code execution failed: {error_type}: {error_message}")
        log_message(f"Error category: {error_category}")
        log_message(f"Full traceback: {full_traceback}")

        # Build comprehensive error response for n8n
        error_response = {
            # PRIMARY EXECUTION STATUS - USE THIS IN N8N
            'code_executed': False,
            'execution_status': 'failed',
            
            # Error classification for n8n decision making
            'error_category': error_category,
            'error_type': error_type,
            'error_message': error_message,
            'error_line': error_line,
            
            # Detailed error info for LLM to fix
            'error_traceback': full_traceback,
            'problematic_code_section': problematic_code_section,
            'original_code': code,
            'code_length': len(code),
            
            # Suggestions for fix based on error category
            'fix_suggestions': get_fix_suggestions(error_category, error_type, error_message),
            
            # Blender context at time of error
            'blender_context': {
                'scene_available': bpy.context.scene is not None,
                'view_layer_available': bpy.context.view_layer is not None,
                'active_object': bpy.context.active_object.name if bpy.context.active_object else None,
                'mode': getattr(bpy.context, 'mode', 'UNKNOWN'),
                'selected_objects_count': len(bpy.context.selected_objects) if bpy.context.selected_objects else 0
            },
            
            # Scene state for context
            'scene_info': scene_info,
            
            # Metadata
            'timestamp': time.time(),
            'blender_version': bpy.app.version_string,
            
            # Legacy fields for backward compatibility
            'status': 'code_execution_failed',
            'execution': 'no',
            'message': f'{error_category}: {error_type} - {error_message}'
        }

        # DISABLED: Synchronous webhook now handles response directly
        # send_result_to_n8n(error_response)
        bpy.context.scene.ai_generator_props.generation_status = f"Execution failed: {str(e)[:50]}..."
        return False

# -------------------------------------------------------------------
# HTTP Server Components
# -------------------------------------------------------------------

class WebhookHandler(BaseHTTPRequestHandler):
    """Webhook handler with SYNCHRONOUS code execution - waits for result before responding"""
    
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 1024 * 1024:  # 1MB limit
                self._send_error_response(413, "Request too large")
                return

            post_data = self.rfile.read(content_length)
            try:
                payload = json.loads(post_data.decode('utf-8'))
            except json.JSONDecodeError:
                self._send_error_response(400, "Invalid JSON", "JSONDecodeError")
                return
            
            code = payload.get('code', '').strip() if payload.get('code') else None
            
            if code:
                # ===== SYNCHRONOUS CODE EXECUTION =====
                # This BLOCKS until execution completes and returns actual result
                
                if len(code) == 0:
                    self._send_error_response(400, "Empty code provided", "ValueError")
                    return
                
                log_message(f"📥 Received code ({len(code)} chars), executing synchronously...")
                
                # Get current scene info
                scene_info = get_detailed_scene_info()
                
                # ⚡ SYNCHRONOUS EXECUTION - Blocks until complete
                result = execute_code_synchronously(code, scene_info)
                
                # Send actual execution result to n8n
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                
                response_json = json.dumps(result, ensure_ascii=False, default=str)
                self.wfile.write(response_json.encode('utf-8'))
                
                status_icon = "✅" if result.get('code_executed') else "❌"
                log_message(f"{status_icon} Execution complete: {result.get('execution_status')} - code_executed={result.get('code_executed')}")
                
            else:
                # Regular prompt processing (non-blocking)
                JOB_QUEUE.put(payload)
                scene_info = get_detailed_scene_info()
                response = {
                    "status": "accepted",
                    "message": "Prompt received and queued for processing",
                    "timestamp": time.time(),
                    "current_scene": scene_info,
                    "scene_summary": format_scene_summary(scene_info),
                    "execution": "processing"
                }
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(response, indent=2).encode('utf-8'))
                log_message(f"📥 Received prompt, queued for processing")
            
        except Exception as e:
            log_message(f"❌ Webhook error: {str(e)}")
            self._send_error_response(500, str(e), type(e).__name__)
    
    def _send_error_response(self, status_code, message, error_type="Error"):
        """Send a standardized error response"""
        error_response = {
            "code_executed": False,
            "execution_status": "failed",
            "error_category": "WEBHOOK_ERROR",
            "error_type": error_type,
            "error_message": message,
            "fix_suggestions": ["Check request format", "Ensure valid JSON", "Include 'code' field"]
        }
        
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(error_response).encode('utf-8'))

    def do_GET(self):
        """Enhanced health check endpoint"""
        try:
            scene_info = get_detailed_scene_info()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            status = {
                "service": "AI 3D Generator Pro (Enhanced - Unified Context)",
                "status": "healthy",
                "version": bl_info["version"],
                "timestamp": time.time(),
                "queue_sizes": {
                    "job_queue": JOB_QUEUE.qsize(),
                    "code_queue": CODE_EXECUTION_QUEUE.qsize(),
                    "result_queue": RESULT_QUEUE.qsize()
                },
                "current_scene": scene_info,
                "scene_summary": format_scene_summary(scene_info),
                "execution": "ready",
                "blender_version": bpy.app.version_string,
                "python_version": f"{bpy.app.version[0]}.{bpy.app.version[1]}",
                "unified_context_fix": True
            }
            self.wfile.write(json.dumps(status, indent=2).encode('utf-8'))
        except Exception as e:
            self.send_error(500, f"Health check failed: {str(e)}")

    def do_OPTIONS(self):
        """Handle preflight CORS requests"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        """Override to control logging"""
        prefs = get_preferences()
        if prefs and prefs.enable_logging:
            print(f"[AI3D-HTTP] {format % args}")

def get_preferences():
    """Safe way to get addon preferences"""
    try:
        return bpy.context.preferences.addons[__name__].preferences
    except:
        return None

def log_message(message):
    """Enhanced centralized logging"""
    prefs = get_preferences()
    if prefs and prefs.enable_logging:
        timestamp = time.strftime("%H:%M:%S", time.localtime())
        print(f"[AI3D {timestamp}] {message}")

# -------------------------------------------------------------------
# Enhanced n8n Communication
# -------------------------------------------------------------------

def send_prompt_to_n8n(prompt, complexity='MEDIUM', include_scene_context=True, update=False):
    """Enhanced prompt sending with better error handling"""
    prefs = get_preferences()
    if not prefs or not prefs.n8n_workflow_url:
        log_message("n8n workflow URL not configured")
        return False

    try:
        scene_info = get_detailed_scene_info()
        data = {
            "prompt": prompt,
            "complexity": complexity,
            "timestamp": time.time(),
            "source": "blender_addon_enhanced_unified",
            "callback_url": f"http://127.0.0.1:{prefs.listen_port}",
            "blender_version": bpy.app.version_string,
            "addon_version": bl_info["version"],
            "update": "yes" if update else "no",
            "current_scene": scene_info if include_scene_context else {},
            "scene_summary": format_scene_summary(scene_info) if include_scene_context else "",
            "enhanced_features": {
                "math_support": True,
                "bmesh_support": True,
                "comprehensive_context": True,
                "error_reporting": "enhanced",
                "unified_context_execution": True
            }
        }

        log_message(f"Sending {'update' if update else 'generation'} prompt to n8n: {prompt[:50]}...")
        
        response = requests.post(
            prefs.n8n_workflow_url,
            json=data,
            timeout=30,
            headers={
                'Content-Type': 'application/json',
                'User-Agent': f'Blender-AI3D-Generator/{".".join(map(str, bl_info["version"]))}',
                'X-Blender-Version': bpy.app.version_string
            }
        )

        if response.status_code == 200:
            log_message(f"Successfully sent prompt to n8n. Response: {response.text[:200]}...")
            return True
        else:
            log_message(f"n8n responded with status {response.status_code}: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        log_message("Timeout sending prompt to n8n (30s limit)")
        return False
    except requests.exceptions.ConnectionError:
        log_message("Connection error - is n8n running and reachable?")
        return False
    except Exception as e:
        log_message(f"Failed to send prompt to n8n: {str(e)}")
        return False

# -------------------------------------------------------------------
# Enhanced Queue Processing
# -------------------------------------------------------------------

def queue_poller():
    """Enhanced queue processing with better resource management"""
    processed_jobs = 0
    max_jobs_per_cycle = 3

    # Process code execution queue (highest priority)
    while not CODE_EXECUTION_QUEUE.empty() and processed_jobs < 2:
        try:
            execution_data = CODE_EXECUTION_QUEUE.get_nowait()
            log_message(f"Executing code on main thread with unified context (length: {len(execution_data['code'])} chars)...")
            safe_execute_code(execution_data['code'], execution_data['scene_info'])
            processed_jobs += 1
        except queue.Empty:
            break
        except Exception as e:
            log_message(f"Main thread execution error: {e}")

    # Process regular job queue
    while not JOB_QUEUE.empty() and processed_jobs < max_jobs_per_cycle:
        try:
            payload = JOB_QUEUE.get_nowait()
            process_webhook_payload(payload)
            processed_jobs += 1
        except queue.Empty:
            break

    # Clean up result queue
    cleaned = 0
    while not RESULT_QUEUE.empty() and cleaned < 10:
        try:
            RESULT_QUEUE.get_nowait()
            cleaned += 1
        except queue.Empty:
            break

    return 0.1  # Continue polling every 100ms

def process_webhook_payload(payload):
    """Enhanced payload processing with better validation"""
    log_message(f"Processing payload type: {'code' if payload.get('code') else 'prompt'}")
    scene_info = get_detailed_scene_info()

    # Handle code execution
    code = payload.get('code')
    if code:
        try:
            # Validate code before execution
            if len(code.strip()) == 0:
                raise ValueError("Empty code provided")
            if len(code) > 50000:  # 50KB limit
                raise ValueError(f"Code too large: {len(code)} characters")

            bpy.context.scene.ai_generator_props.generation_status = "Queueing code for unified context execution..."
            execute_code_on_main_thread(code, scene_info)
            log_message("Code successfully queued for main thread unified context execution")
            
        except Exception as e:
            error_msg = f"Failed to queue code: {str(e)}"
            log_message(error_msg)
            bpy.context.scene.ai_generator_props.generation_status = error_msg
            send_result_to_n8n({
                'code_executed': False,
                'execution_status': 'failed',
                'status': 'queue_error',
                'error_category': 'QUEUE_ERROR',
                'error_type': type(e).__name__,
                'error_message': str(e),
                'error': str(e),
                'scene_info': scene_info,
                'message': error_msg,
                'execution': 'no',
                'fix_suggestions': ['Check if code is valid Python', 'Ensure code size is under 50KB'],
                'timestamp': time.time()
            })
        return

    # Handle regular prompts
    prompt = (payload.get('prompt') or
              payload.get('message') or
              payload.get('text') or
              payload.get('description') or
              str(payload))
    
    if len(prompt) > 10000:
        prompt = prompt[:10000] + "..."

    scene_props = bpy.context.scene.ai_generator_props
    scene_props.generation_status = f"Processing: {prompt[:30]}..."

    job_id = f"job_{int(time.time())}_{random.randint(1000, 9999)}"
    complexity = scene_props.complexity_level

    # Send acknowledgment
    send_result_to_n8n({
        'status': 'accepted',
        'job_id': job_id,
        'prompt': prompt,
        'message': 'Generation started',
        'scene_context': scene_info,
        'scene_summary': format_scene_summary(scene_info),
        'execution': 'processing',
        'timestamp': time.time()
    })

def send_result_to_n8n(data):
    """Enhanced result sending with retry logic"""
    prefs = get_preferences()
    if not prefs or not prefs.post_back_url:
        log_message("No post_back_url configured - cannot send result")
        return

    max_retries = 3
    for attempt in range(max_retries):
        try:
            log_message(f"Sending result to n8n (attempt {attempt + 1}): {data.get('status', 'unknown')} - {data.get('execution', 'unknown')}")
            
            response = requests.post(
                prefs.post_back_url,
                json=data,
                timeout=15,
                headers={
                    'Content-Type': 'application/json',
                    'X-Attempt': str(attempt + 1),
                    'X-Blender-Version': bpy.app.version_string
                }
            )
            
            if response.status_code == 200:
                log_message(f"Result sent successfully to n8n: {data['status']}")
                return True
            else:
                log_message(f"n8n responded with status {response.status_code}: {response.text}")
                if attempt < max_retries - 1:
                    time.sleep(0.5 * (attempt + 1))  # Exponential backoff
                    continue
                return False
                
        except requests.exceptions.Timeout:
            log_message(f"Timeout sending result to n8n (attempt {attempt + 1})")
            if attempt < max_retries - 1:
                time.sleep(1.0 * (attempt + 1))
                continue
        except requests.exceptions.ConnectionError:
            log_message(f"Connection error sending result to n8n (attempt {attempt + 1})")
            if attempt < max_retries - 1:
                time.sleep(1.0 * (attempt + 1))
                continue
        except Exception as e:
            log_message(f"Failed to send result to n8n (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(0.5 * (attempt + 1))
                continue
    
    log_message("Failed to send result to n8n after all retry attempts")
    return False


def send_error_response_to_n8n(error_type: str, error_message: str, code: str = None, scene_info: dict = None):
    """Helper function to send standardized error responses to n8n"""
    error_category = categorize_blender_error(error_type, error_message, '')
    
    error_response = {
        'code_executed': False,
        'execution_status': 'failed',
        'error_category': error_category,
        'error_type': error_type,
        'error_message': error_message,
        'original_code': code,
        'fix_suggestions': get_fix_suggestions(error_category, error_type, error_message),
        'scene_info': scene_info,
        'timestamp': time.time(),
        'blender_version': bpy.app.version_string,
        'status': 'code_execution_failed',
        'execution': 'no',
        'message': f'{error_category}: {error_type} - {error_message}'
    }
    
    return send_result_to_n8n(error_response)


# -------------------------------------------------------------------
# Enhanced Server Management
# -------------------------------------------------------------------

def start_server(port):
    """Enhanced server startup with better error handling"""
    global HTTPD, SERVER_THREAD
    if HTTPD:
        log_message("Server already running")
        return False

    try:
        # Check if port is available
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        
        if result == 0:
            log_message(f"Port {port} is already in use")
            return False

        HTTPD = ThreadingHTTPServer(("127.0.0.1", port), WebhookHandler)
        HTTPD.timeout = 1.0  # Allow for clean shutdown
        
        SERVER_THREAD = threading.Thread(
            target=HTTPD.serve_forever,
            name="AI3D_WebhookServer_Enhanced_Unified",
            daemon=True
        )
        SERVER_THREAD.start()
        
        log_message(f"Enhanced unified context webhook server started on http://127.0.0.1:{port}")
        
        # Start the queue poller
        if not bpy.app.timers.is_registered(queue_poller):
            bpy.app.timers.register(queue_poller, first_interval=0.1)
            
        return True
        
    except OSError as e:
        if e.errno == 48:  # Address already in use
            log_message(f"Port {port} is already in use by another application")
        else:
            log_message(f"OS error starting server: {e}")
        return False
    except Exception as e:
        log_message(f"Failed to start server: {e}")
        return False

def stop_server():
    """Enhanced server shutdown with cleanup"""
    global HTTPD, SERVER_THREAD
    
    if HTTPD:
        try:
            HTTPD.shutdown()
            HTTPD.server_close()
            log_message("Webhook server stopped")
        except Exception as e:
            log_message(f"Error stopping server: {e}")
        finally:
            HTTPD = None
            SERVER_THREAD = None
    
    # Stop the queue poller
    if bpy.app.timers.is_registered(queue_poller):
        bpy.app.timers.unregister(queue_poller)
    
    # Clear all queues
    clear_all_queues()
    return True

def clear_all_queues():
    """Clear all queues and reset status"""
    queues = [JOB_QUEUE, RESULT_QUEUE, CODE_EXECUTION_QUEUE]
    total_cleared = 0
    
    for q in queues:
        count = 0
        while not q.empty():
            try:
                q.get_nowait()
                count += 1
            except queue.Empty:
                break
        total_cleared += count
    
    if total_cleared > 0:
        log_message(f"Cleared {total_cleared} items from queues")
    
    # Reset status
    try:
        bpy.context.scene.ai_generator_props.generation_status = "Ready"
    except:
        pass

# -------------------------------------------------------------------
# Enhanced Operators
# -------------------------------------------------------------------

class AI_OT_generate_model(Operator):
    """Generate 3D model from AI prompt via n8n with enhanced validation"""
    bl_idname = "ai.generate_3d_model"
    bl_label = "Generate"
    bl_description = "Generate a new 3D model based on the prompt via n8n"
    bl_options = {'REGISTER'}

    def execute(self, context):
        scene_props = context.scene.ai_generator_props
        prompt = scene_props.ai_prompt.strip()
        
        if not prompt:
            self.report({'ERROR'}, "Please enter a prompt")
            return {'CANCELLED'}
        
        if len(prompt) < 10:
            self.report({'WARNING'}, "Prompt seems very short - consider adding more detail")
        
        if not HTTPD:
            self.report({'ERROR'}, "Webhook server not running - start it first")
            return {'CANCELLED'}

        scene_props.generation_status = "Sending generation request to n8n..."
        success = send_prompt_to_n8n(
            prompt,
            scene_props.complexity_level,
            scene_props.include_scene_context,
            update=False
        )

        if success:
            scene_props.generation_status = "Request sent - waiting for n8n response..."
            self.report({'INFO'}, f"Generation prompt sent to n8n: '{prompt[:50]}...'")
        else:
            scene_props.generation_status = "Failed to send request to n8n"
            self.report({'ERROR'}, "Failed to send to n8n - check console and n8n connection")
            
        return {'FINISHED'}

class AI_OT_update_model(Operator):
    """Update current objects based on prompt with enhanced validation"""
    bl_idname = "ai.update_3d_model"
    bl_label = "Update"
    bl_description = "Update current objects based on the prompt via n8n"
    bl_options = {'REGISTER'}

    def execute(self, context):
        scene_props = context.scene.ai_generator_props
        prompt = scene_props.ai_prompt.strip()
        
        if not prompt:
            self.report({'ERROR'}, "Please enter a prompt")
            return {'CANCELLED'}
        
        if not HTTPD:
            self.report({'ERROR'}, "Webhook server not running - start it first")
            return {'CANCELLED'}
        
        # Check if there are objects to update
        if len(context.scene.objects) == 0:
            self.report({'WARNING'}, "No objects in scene to update")

        scene_props.generation_status = "Sending update request to n8n..."
        success = send_prompt_to_n8n(
            prompt,
            scene_props.complexity_level,
            scene_props.include_scene_context,
            update=True
        )

        if success:
            scene_props.generation_status = "Update request sent - waiting for n8n response..."
            self.report({'INFO'}, f"Update prompt sent to n8n: '{prompt[:50]}...'")
        else:
            scene_props.generation_status = "Failed to send update request to n8n"
            self.report({'ERROR'}, "Failed to send to n8n - check console and n8n connection")
            
        return {'FINISHED'}

class AI_OT_start_server(Operator):
    """Start n8n webhook server with validation"""
    bl_idname = "ai.start_server"
    bl_label = "Start Webhook Server"
    bl_description = "Start HTTP server to receive n8n webhooks with unified context execution"

    def execute(self, context):
        prefs = context.preferences.addons[__name__].preferences
        
        if HTTPD:
            self.report({'WARNING'}, "Server is already running")
            return {'FINISHED'}
        
        if start_server(prefs.listen_port):
            self.report({'INFO'}, f"Enhanced unified context server started on port {prefs.listen_port}")
        else:
            self.report({'ERROR'}, f"Failed to start server on port {prefs.listen_port} - check console")
            
        return {'FINISHED'}

class AI_OT_stop_server(Operator):
    """Stop n8n webhook server with cleanup"""
    bl_idname = "ai.stop_server"
    bl_label = "Stop Webhook Server"
    bl_description = "Stop HTTP server and clear queues"

    def execute(self, context):
        if not HTTPD:
            self.report({'WARNING'}, "Server was not running")
            return {'FINISHED'}
        
        if stop_server():
            self.report({'INFO'}, "Server stopped and queues cleared")
        else:
            self.report({'WARNING'}, "Server stop completed with warnings")
            
        return {'FINISHED'}

class AI_OT_clear_status(Operator):
    """Clear generation status and reset"""
    bl_idname = "ai.clear_status"
    bl_label = "Clear Status"
    bl_description = "Clear the current generation status"

    def execute(self, context):
        context.scene.ai_generator_props.generation_status = "Ready"
        clear_all_queues()
        self.report({'INFO'}, "Status cleared and queues reset")
        return {'FINISHED'}

class AI_OT_test_connection(Operator):
    """Test connection to n8n"""
    bl_idname = "ai.test_connection"
    bl_label = "Test n8n Connection"
    bl_description = "Test connectivity to n8n workflow URL"

    def execute(self, context):
        prefs = context.preferences.addons[__name__].preferences
        
        if not prefs.n8n_workflow_url:
            self.report({'ERROR'}, "n8n workflow URL not configured")
            return {'CANCELLED'}
        
        try:
            response = requests.get(prefs.n8n_workflow_url, timeout=5)
            if response.status_code in [200, 404, 405]:  # 405 is method not allowed, but means server is reachable
                self.report({'INFO'}, f"n8n server is reachable (status: {response.status_code})")
            else:
                self.report({'WARNING'}, f"n8n server responded with status: {response.status_code}")
        except requests.exceptions.ConnectionError:
            self.report({'ERROR'}, "Cannot connect to n8n server - check if it's running")
        except requests.exceptions.Timeout:
            self.report({'ERROR'}, "Connection to n8n server timed out")
        except Exception as e:
            self.report({'ERROR'}, f"Connection test failed: {str(e)}")
            
        return {'FINISHED'}

class AI_OT_test_unified_context(Operator):
    """Test unified context execution with sample code"""
    bl_idname = "ai.test_unified_context"
    bl_label = "Test Unified Context"
    bl_description = "Test the unified context execution with sample function definition and call"

    def execute(self, context):
        # Sample test code that defines a function and then calls it
        test_code = '''
def create_test_cube(name="TestCube", size=2.0, location=(0, 0, 0)):
    import bpy
    import bmesh
    from mathutils import Vector
    
    # Create bmesh cube
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=size)
    
    # Create mesh from bmesh
    me = bpy.data.meshes.new(name + "_mesh")
    bm.to_mesh(me)
    bm.free()
    
    # Create object
    obj = bpy.data.objects.new(name, me)
    obj.location = Vector(location)
    
    # Link to scene
    bpy.context.scene.collection.objects.link(obj)
    return obj

# Call the function we just defined
test_obj = create_test_cube("UnifiedContextTest", size=1.5, location=(2, 0, 0))
print(f"Created test object: {test_obj.name}")
'''
        
        try:
            scene_info = get_detailed_scene_info()
            success = safe_execute_code(test_code, scene_info)
            if success:
                self.report({'INFO'}, "Unified context test successful - check for TestCube object")
            else:
                self.report({'ERROR'}, "Unified context test failed - check console")
        except Exception as e:
            self.report({'ERROR'}, f"Test execution error: {str(e)}")
            
        return {'FINISHED'}

# -------------------------------------------------------------------
# Enhanced UI Panel
# -------------------------------------------------------------------

class AI_PT_generator_panel(Panel):
    """Enhanced AI Generator Panel with Unified Context Features"""
    bl_label = "DreamMesh"
    bl_idname = "VIEW3D_PT_ai_generator_pro"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'DreamMesh'

    def draw(self, context):
        layout = self.layout
        scene_props = context.scene.ai_generator_props
        prefs = context.preferences.addons[__name__].preferences

        # Webhook Server Box
        box = layout.box()
        box.label(text="Webhook Server (Unified Context)", icon='WORLD_DATA')
        row = box.row(align=True)
        server_running = HTTPD is not None
        if server_running:
            row.operator("ai.stop_server", text="Stop Server", icon='PAUSE')
            box.label(text=f"Listening on port {prefs.listen_port}", icon='CHECKMARK')
            # Show queue status
            job_queue_size = JOB_QUEUE.qsize()
            code_queue_size = CODE_EXECUTION_QUEUE.qsize()
            if job_queue_size > 0 or code_queue_size > 0:
                box.label(text=f"Jobs: {job_queue_size}, Code: {code_queue_size}", icon='TIME')
        else:
            row.operator("ai.start_server", text="Start Server", icon='PLAY')
            box.label(text="Server stopped", icon='RADIOBUT_OFF')

        # Generate Model Box
        box = layout.box()
        box.label(text="Generate Model", icon='MESH_CUBE')
        box.prop(scene_props, "ai_prompt", text="")
        row = box.row(align=True)
        row.prop(scene_props, "complexity_level", text="")
        row.prop(scene_props, "auto_material", text="", icon='MATERIAL')
        box.prop(scene_props, "include_scene_context", text="Include Scene Context")
        button_row = box.row(align=True)
        button_row.operator("ai.generate_3d_model", text="Generate", icon='ADD')
        button_row.operator("ai.update_3d_model", text="Update", icon='FILE_REFRESH')

        # Status display with improved feedback
        if scene_props.generation_status != "Ready":
            status_box = box.box()
            row = status_box.row()
            # Choose icon based on status
            if "error" in scene_props.generation_status.lower() or "failed" in scene_props.generation_status.lower():
                icon = 'ERROR'
            elif "success" in scene_props.generation_status.lower() or "completed" in scene_props.generation_status.lower():
                icon = 'CHECKMARK'
            elif "executing" in scene_props.generation_status.lower() or "processing" in scene_props.generation_status.lower():
                icon = 'TIME'
            else:
                icon = 'INFO'
            row.label(text=scene_props.generation_status, icon=icon)

        # Debug/Test Box
        box = layout.box()
        box.label(text="Debug & Testing", icon='CONSOLE')
        row = box.row(align=True)
        row.operator("ai.test_connection", text="Test n8n", icon='LINKED')
        row.operator("ai.test_unified_context", text="Test Context", icon='EXPERIMENTAL')
        box.operator("ai.clear_status", text="Clear Status", icon='X')

# -------------------------------------------------------------------
# Enhanced Registration & Cleanup
# -------------------------------------------------------------------

@persistent
def load_post_handler(dummy):
    """Enhanced file load event handler"""
    log_message("File loaded - cleaning up AI Generator resources")
    cleanup_on_load()

def cleanup_on_load():
    """Enhanced cleanup when loading new file"""
    global HTTPD, SERVER_THREAD
    
    # Stop server if running
    if HTTPD:
        log_message("Stopping server due to file load")
        stop_server()
    
    # Clear all queues
    clear_all_queues()
    
    # Reset properties
    try:
        if hasattr(bpy.context.scene, 'ai_generator_props'):
            bpy.context.scene.ai_generator_props.generation_status = "Ready"
    except:
        pass
    
    log_message("Cleanup completed")

# Class registration list
CLASSES = [
    AIGeneratorProperties,
    AIGeneratorPrefs,
    AI_OT_generate_model,
    AI_OT_update_model,
    AI_OT_start_server,
    AI_OT_stop_server,
    AI_OT_clear_status,
    AI_OT_test_connection,
    AI_OT_test_unified_context,
    AI_PT_generator_panel,
]

def register():
    """Enhanced registration with better error handling"""
    try:
        # Register all classes
        for cls in CLASSES:
            bpy.utils.register_class(cls)
        
        # Add scene property
        bpy.types.Scene.ai_generator_props = bpy.props.PointerProperty(type=AIGeneratorProperties)
        
        # Add load handler
        if load_post_handler not in bpy.app.handlers.load_post:
            bpy.app.handlers.load_post.append(load_post_handler)
        
        # Auto-start server if enabled
        try:
            prefs = bpy.context.preferences.addons[__name__].preferences
            if prefs and prefs.auto_start_server:
                if start_server(prefs.listen_port):
                    log_message("Auto-started unified context server on registration")
                else:
                    log_message("Failed to auto-start server")
        except Exception as e:
            log_message(f"Auto-start error: {e}")
        
        log_message("AI 3D Generator Pro (Enhanced + Unified Context) registered successfully")
        
    except Exception as e:
        print(f"Registration error: {e}")
        raise

def unregister():
    """Enhanced unregistration with thorough cleanup"""
    try:
        # Clean up resources first
        cleanup_on_load()
        
        # Remove load handler
        if load_post_handler in bpy.app.handlers.load_post:
            bpy.app.handlers.load_post.remove(load_post_handler)
        
        # Remove scene property
        if hasattr(bpy.types.Scene, 'ai_generator_props'):
            del bpy.types.Scene.ai_generator_props
        
        # Unregister classes in reverse order
        for cls in reversed(CLASSES):
            try:
                bpy.utils.unregister_class(cls)
            except Exception as e:
                log_message(f"Error unregistering {cls}: {e}")
        
        log_message("AI 3D Generator Pro (Enhanced + Unified) unregistered successfully")
        
    except Exception as e:
        print(f"Unregistration error: {e}")

# Entry point for direct execution
if __name__ == "__main__":
    register()