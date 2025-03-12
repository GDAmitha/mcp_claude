from mcp.server.fastmcp import FastMCP, Context, Image
import io
from PIL import Image as PILImage
import base64
import sys
import os
import traceback
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("pymol_server")

# Print startup information to help with debugging
logger.info(f"Starting PyMOL server with Python {sys.version}")
logger.info(f"Current working directory: {os.getcwd()}")
logger.info(f"PATH environment: {os.environ.get('PATH', 'Not set')}")
logger.info(f"PYTHONPATH environment: {os.environ.get('PYTHONPATH', 'Not set')}")

# Import pymol in the lifespan handler to ensure proper initialization
@asynccontextmanager
async def pymol_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Initialize PyMOL and clean up afterwards"""
    logger.info("Starting PyMOL initialization")
    try:
        # Try to import PyMOL
        logger.info("Attempting to import pymol")
        try:
            import pymol
            logger.info(f"PyMOL imported successfully: {pymol}")
        except ImportError as e:
            logger.error(f"Failed to import pymol: {e}")
            logger.error(f"Python path: {sys.path}")
            raise
        
        # Try to import cmd module
        logger.info("Attempting to import pymol.cmd")
        try:
            from pymol import cmd
            logger.info("PyMOL cmd module imported successfully")
        except ImportError as e:
            logger.error(f"Failed to import pymol.cmd: {e}")
            raise
        
        # Launch PyMOL in command-line mode
        logger.info("Launching PyMOL in quiet mode")
        try:
            pymol.finish_launching(['pymol', '-cq'])  # Quiet and no GUI mode
            logger.info("PyMOL launched successfully")
        except Exception as e:
            logger.error(f"Failed to launch PyMOL: {e}")
            logger.error(traceback.format_exc())
            raise
        
        # Configure PyMOL settings
        logger.info("Configuring PyMOL settings")
        cmd.set("retain_order", 1)  # Preserve atom ordering
        cmd.set("pdb_use_ter_records", 1)  # Use TER records in PDB files
        logger.info("PyMOL settings configured successfully")
        
        # Provide context with PyMOL cmd module
        logger.info("PyMOL initialization completed successfully")
        yield {"cmd": cmd}
        
    except Exception as e:
        logger.error(f"Error during PyMOL initialization: {str(e)}")
        logger.error(traceback.format_exc())
        yield {"error": str(e), "traceback": traceback.format_exc()}
    finally:
        # Clean up PyMOL if initialized
        logger.info("Cleaning up PyMOL")
        try:
            from pymol import cmd
            cmd.quit()
            logger.info("PyMOL cleanup completed")
        except Exception as e:
            logger.error(f"Error during PyMOL cleanup: {str(e)}")
            logger.error(traceback.format_exc())

# Create an MCP server for PyMOL with the lifespan handler
logger.info("Creating FastMCP server for PyMOL")
mcp = FastMCP("PyMOL", lifespan=pymol_lifespan)
logger.info("FastMCP server created successfully")

# Helper function to safely access PyMOL cmd
def get_cmd(ctx: Context) -> Any:
    """Get the PyMOL cmd object from context"""
    if "error" in ctx.request_context.lifespan_context:
        error_msg = ctx.request_context.lifespan_context.get("error")
        traceback_info = ctx.request_context.lifespan_context.get("traceback", "")
        logger.error(f"PyMOL not properly initialized: {error_msg}")
        logger.error(f"Traceback: {traceback_info}")
        raise RuntimeError(f"PyMOL not properly initialized: {error_msg}")
        
    cmd = ctx.request_context.lifespan_context.get("cmd")
    if cmd is None:
        logger.error("PyMOL cmd object not found in context")
        raise RuntimeError("PyMOL cmd object not found in context")
        
    return cmd

# Structure Loading Tools
@mcp.tool()
def fetch_structure(ctx: Context, pdb_id: str) -> str:
    """
    Fetch a structure from the Protein Data Bank.
    
    Args:
        ctx: MCP context
        pdb_id: The 4-character PDB ID code (e.g., '1dn2')
        
    Returns:
        A message indicating the result of the operation
    """
    try:
        logger.info(f"Fetching structure with PDB ID: {pdb_id}")
        cmd = get_cmd(ctx)
        result = cmd.fetch(pdb_id)
        logger.info(f"Successfully fetched PDB ID {pdb_id}")
        return f"Successfully fetched {pdb_id}"
    except Exception as e:
        logger.error(f"Error fetching PDB ID {pdb_id}: {str(e)}")
        logger.error(traceback.format_exc())
        return f"Error fetching {pdb_id}: {str(e)}"

@mcp.tool()
def load_structure(file_path: str, ctx: Context) -> str:
    """
    Load a structure from a local file.
    
    Args:
        file_path: Path to the structure file (e.g., PDB, CIF, MOL, etc.)
        
    Returns:
        A message indicating the result of the operation
    """
    try:
        cmd = get_cmd(ctx)
        # Use absolute path if provided path is relative
        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)
        
        result = cmd.load(file_path)
        return f"Successfully loaded {file_path}"
    except Exception as e:
        return f"Error loading {file_path}: {str(e)}"

# Visualization Tools
@mcp.tool()
def show_representation(ctx: Context, representation: str, selection: str = "all") -> str:
    """
    Show a representation for a selection.
    
    Args:
        ctx: MCP context
        representation: Type of representation (cartoon, surface, sticks, lines, spheres, etc.)
        selection: PyMOL selection expression (default: "all")
        
    Returns:
        A message indicating the result of the operation
    """
    try:
        cmd = get_cmd(ctx)
        cmd.show(representation, selection)
        return f"Showing {representation} for {selection}"
    except Exception as e:
        return f"Error showing {representation} for {selection}: {str(e)}"

@mcp.tool()
def hide_representation(ctx: Context, representation: str, selection: str = "all") -> str:
    """
    Hide a representation for a selection.
    
    Args:
        ctx: MCP context
        representation: Type of representation (cartoon, surface, sticks, lines, spheres, etc.)
        selection: PyMOL selection expression (default: "all")
        
    Returns:
        A message indicating the result of the operation
    """
    try:
        cmd = get_cmd(ctx)
        cmd.hide(representation, selection)
        return f"Hiding {representation} for {selection}"
    except Exception as e:
        return f"Error hiding {representation} for {selection}: {str(e)}"

@mcp.tool()
def color_selection(ctx: Context, color: str, selection: str = "all") -> str:
    """
    Color a selection.
    
    Args:
        ctx: MCP context
        color: Color name or RGB/RGBA hex code
        selection: PyMOL selection expression (default: "all")
        
    Returns:
        A message indicating the result of the operation
    """
    try:
        cmd = get_cmd(ctx)
        cmd.color(color, selection)
        return f"Colored {selection} with {color}"
    except Exception as e:
        return f"Error coloring {selection} with {color}: {str(e)}"

# Selection Tools
@mcp.tool()
def create_selection(name: str, selection: str, ctx: Context) -> str:
    """
    Create a named selection.
    
    Args:
        name: Name for the selection
        selection: PyMOL selection expression
        
    Returns:
        A message indicating the result of the operation
    """
    try:
        cmd = get_cmd(ctx)
        result = cmd.select(name, selection)
        return f"Created selection '{name}' for {selection} with {result} atoms"
    except Exception as e:
        return f"Error creating selection '{name}' for {selection}: {str(e)}"

@mcp.tool()
def enable_object(name: str, ctx: Context) -> str:
    """
    Enable (show) an object or selection.
    
    Args:
        name: Name of the object or selection
        
    Returns:
        A message indicating the result of the operation
    """
    try:
        cmd = get_cmd(ctx)
        cmd.enable(name)
        return f"Enabled {name}"
    except Exception as e:
        return f"Error enabling {name}: {str(e)}"

@mcp.tool()
def disable_object(name: str, ctx: Context) -> str:
    """
    Disable (hide) an object or selection.
    
    Args:
        name: Name of the object or selection
        
    Returns:
        A message indicating the result of the operation
    """
    try:
        cmd = get_cmd(ctx)
        cmd.disable(name)
        return f"Disabled {name}"
    except Exception as e:
        return f"Error disabling {name}: {str(e)}"

# Camera Tools
@mcp.tool()
def zoom_selection(ctx: Context, selection: str = "all") -> str:
    """
    Zoom the camera on a selection.
    
    Args:
        ctx: MCP context
        selection: PyMOL selection expression (default: "all")
        
    Returns:
        A message indicating the result of the operation
    """
    try:
        cmd = get_cmd(ctx)
        cmd.zoom(selection)
        return f"Zoomed on {selection}"
    except Exception as e:
        return f"Error zooming on {selection}: {str(e)}"

# Measurement Tools
@mcp.tool()
def measure_distance(ctx: Context, atom1: str, atom2: str, name: str = "dist01") -> str:
    """
    Measure the distance between two atoms.
    
    Args:
        ctx: MCP context
        atom1: First atom selection
        atom2: Second atom selection
        name: Name for the measurement object (default: "dist01")
        
    Returns:
        A message with the distance measurement
    """
    try:
        cmd = get_cmd(ctx)
        result = cmd.distance(name, atom1, atom2)
        return f"Distance between {atom1} and {atom2} is {result:.2f} Å"
    except Exception as e:
        return f"Error measuring distance: {str(e)}"

@mcp.tool()
def measure_angle(ctx: Context, atom1: str, atom2: str, atom3: str, name: str = "angle01") -> str:
    """
    Measure the angle between three atoms.
    
    Args:
        ctx: MCP context
        atom1: First atom selection
        atom2: Second atom selection (vertex)
        atom3: Third atom selection
        name: Name for the measurement object (default: "angle01")
        
    Returns:
        A message with the angle measurement
    """
    try:
        cmd = get_cmd(ctx)
        result = cmd.angle(name, atom1, atom2, atom3)
        return f"Angle between {atom1}, {atom2}, and {atom3} is {result:.2f}°"
    except Exception as e:
        return f"Error measuring angle: {str(e)}"

@mcp.tool()
def measure_dihedral(ctx: Context, atom1: str, atom2: str, atom3: str, atom4: str, name: str = "dihedral01") -> str:
    """
    Measure the dihedral angle between four atoms.
    
    Args:
        ctx: MCP context
        atom1: First atom selection
        atom2: Second atom selection
        atom3: Third atom selection
        atom4: Fourth atom selection
        name: Name for the measurement object (default: "dihedral01")
        
    Returns:
        A message with the dihedral angle measurement
    """
    try:
        cmd = get_cmd(ctx)
        result = cmd.dihedral(name, atom1, atom2, atom3, atom4)
        return f"Dihedral angle between {atom1}, {atom2}, {atom3}, and {atom4} is {result:.2f}°"
    except Exception as e:
        return f"Error measuring dihedral angle: {str(e)}"

# Labeling Tools
@mcp.tool()
def add_label(ctx: Context, selection: str, text: str) -> str:
    """
    Add a label to atoms in a selection.
    
    Args:
        ctx: MCP context
        selection: PyMOL selection expression
        text: Label text or PyMOL expression
        
    Returns:
        A message indicating the result of the operation
    """
    try:
        cmd = get_cmd(ctx)
        cmd.label(selection, text)
        return f"Added label '{text}' to {selection}"
    except Exception as e:
        return f"Error adding label: {str(e)}"

# Image Rendering Tools
@mcp.tool()
def draw_image(ctx: Context, width: int = 1600, height: int = 1200) -> str:
    """
    Prepare an OpenGL-based image.
    
    Args:
        ctx: MCP context
        width: Image width in pixels (default: 1600)
        height: Image height in pixels (default: 1200)
        
    Returns:
        A message indicating the result of the operation
    """
    try:
        cmd = get_cmd(ctx)
        cmd.viewport(width, height)
        cmd.draw()
        return f"Prepared OpenGL image with dimensions {width}x{height}"
    except Exception as e:
        return f"Error preparing image: {str(e)}"

@mcp.tool()
def ray_trace(ctx: Context, width: int = 1200, height: int = 900) -> str:
    """
    Prepare a ray-traced image with better quality than OpenGL.
    
    Args:
        ctx: MCP context
        width: Image width in pixels (default: 1200)
        height: Image height in pixels (default: 900)
        
    Returns:
        A message indicating the result of the operation
    """
    try:
        cmd = get_cmd(ctx)
        cmd.viewport(width, height)
        cmd.ray(width, height)
        return f"Prepared ray-traced image with dimensions {width}x{height}"
    except Exception as e:
        return f"Error ray-tracing: {str(e)}"

@mcp.tool()
def save_png(ctx: Context, filename: str, width: int = 1200, height: int = 900, ray: bool = True) -> str:
    """
    Save the current view as a PNG image.
    
    Args:
        ctx: MCP context
        filename: Output filename
        width: Image width in pixels (default: 1200)
        height: Image height in pixels (default: 900)
        ray: Whether to use ray tracing for better quality (default: True)
        
    Returns:
        A message indicating the result of the operation
    """
    try:
        cmd = get_cmd(ctx)
        # Use absolute path if provided path is relative
        if not os.path.isabs(filename):
            filename = os.path.abspath(filename)
            
        cmd.viewport(width, height)
        if ray:
            cmd.ray(width, height)
        cmd.png(filename)
        return f"Saved PNG image to {filename}"
    except Exception as e:
        return f"Error saving PNG: {str(e)}"

@mcp.tool()
def render_image(ctx: Context, width: int = 1200, height: int = 900, ray_trace: bool = True) -> Image:
    """
    Render the current view as an image and return it directly.
    
    Args:
        ctx: MCP context
        width: Image width in pixels (default: 1200)
        height: Image height in pixels (default: 900)
        ray_trace: Whether to use ray tracing for better quality (default: True)
        
    Returns:
        A rendered image of the current PyMOL view
    """
    try:
        cmd = get_cmd(ctx)
        # Set the viewport size
        cmd.viewport(width, height)
        
        # Ray-trace if requested
        if ray_trace:
            cmd.ray(width, height)
        
        # Get the image as PNG data
        png_data = cmd.png_as_string()
        
        # Return as MCP Image
        return Image(data=png_data, format="png")
    except Exception as e:
        error_msg = f"Error rendering image: {str(e)}"
        # Create a simple error image
        pil_img = PILImage.new('RGB', (400, 100), color=(255, 255, 255))
        img_bytes = io.BytesIO()
        pil_img.save(img_bytes, format='PNG')
        return Image(data=img_bytes.getvalue(), format="png")

# Direct Command Execution
@mcp.tool()
def run_command(command: str, ctx: Context) -> str:
    """
    Run a PyMOL command directly.
    
    Args:
        command: PyMOL command to run
        
    Returns:
        A message indicating the result of the operation
    """
    try:
        cmd = get_cmd(ctx)
        result = cmd.do(command)
        return f"Executed: {command}"
    except Exception as e:
        return f"Error executing '{command}': {str(e)}"

# Info/Status Tools
@mcp.tool()
def list_objects(ctx: Context) -> str:
    """
    List all objects currently loaded in PyMOL.
    
    Returns:
        A string with all loaded objects
    """
    try:
        cmd = get_cmd(ctx)
        objects = cmd.get_names("objects")
        if not objects:
            return "No objects currently loaded in PyMOL."
        
        return "Loaded objects:\n" + "\n".join(objects)
    except Exception as e:
        return f"Error listing objects: {str(e)}"

@mcp.tool()
def list_selections(ctx: Context) -> str:
    """
    List all selections currently defined in PyMOL.
    
    Returns:
        A string with all defined selections
    """
    try:
        cmd = get_cmd(ctx)
        selections = cmd.get_names("selections")
        if not selections:
            return "No selections currently defined in PyMOL."
        
        return "Defined selections:\n" + "\n".join(selections)
    except Exception as e:
        return f"Error listing selections: {str(e)}"

@mcp.tool()
def save_structure(ctx: Context, filename: str, selection: str = "all", state: int = -1) -> str:
    """
    Save a structure to a file.
    
    Args:
        ctx: MCP context
        filename: Output filename
        selection: PyMOL selection to save (default: "all")
        state: State to save (-1 = current) (default: -1)
        
    Returns:
        A message indicating the result of the operation
    """
    try:
        cmd = get_cmd(ctx)
        # Use absolute path if provided path is relative
        if not os.path.isabs(filename):
            filename = os.path.abspath(filename)
            
        cmd.save(filename, selection, state)
        return f"Saved {selection} to {filename}"
    except Exception as e:
        return f"Error saving to {filename}: {str(e)}"

# Helpful Prompts
@mcp.prompt()
def basic_visualization(pdb_id: str) -> str:
    """Create a prompt for basic protein visualization"""
    return f"""
Visualize the protein structure with PDB ID {pdb_id} in the following way:
1. Fetch the structure
2. Show it as cartoon representation
3. Color by secondary structure
4. Show sticks for all ligands
5. Apply a white surface to the protein
6. Zoom to center the view
7. Render a high-quality image
"""

@mcp.prompt()
def binding_site_analysis(pdb_id: str, ligand_name: str = "LIG") -> str:
    """Create a prompt for binding site analysis"""
    return f"""
Analyze the binding site of ligand {ligand_name} in structure {pdb_id}:
1. Fetch the structure
2. Show the protein as cartoon
3. Select the ligand using "resn {ligand_name}"
4. Show the ligand as sticks and color it in magenta
5. Select residues within 5A of the ligand
6. Show those residues as sticks
7. Label them with their residue names and numbers
8. Measure key interactions (distances) between the ligand and binding site residues
9. Render a high-quality image of the binding site
"""

@mcp.prompt()
def custom_command_sequence() -> str:
    """Create a prompt for running a custom sequence of PyMOL commands"""
    return """
Please help me run a series of PyMOL commands to manipulate and visualize my molecule.
I'll provide the commands I want to run, and you can execute them one by one.

For example:
1. fetch 1dn2
2. show cartoon
3. color green, chain A
4. color blue, chain B
5. show sticks, resn ATP
6. zoom
7. render an image
"""

# Resource for session state
@mcp.resource("pymol://session/state")
def get_pymol_state() -> str:
    """
    Get information about the current PyMOL session state including loaded objects, selections, and view.
    
    Returns:
        A text representation of the PyMOL session state
    """
    try:
        logger.info("Getting PyMOL session state")
        # We can't use ctx here because this is a resource function without URI parameters
        # So we need to import cmd directly
        try:
            from pymol import cmd
        except ImportError as e:
            logger.error(f"Failed to import pymol.cmd: {e}")
            return f"Error: PyMOL not properly initialized: {str(e)}"
            
        # Get objects
        objects = cmd.get_names("objects")
        object_info = [f"Object: {obj}" for obj in objects]
        
        # Get selections
        selections = cmd.get_names("selections")
        selection_info = [f"Selection: {sel}" for sel in selections]
        
        # Get current view
        view = cmd.get_view()
        view_str = "View matrix: " + str(view)
        
        # Combine information
        state_info = ["PyMOL Session State:"]
        if object_info:
            state_info.append("\nLoaded Objects:")
            state_info.extend(object_info)
        else:
            state_info.append("\nNo objects loaded.")
            
        if selection_info:
            state_info.append("\nActive Selections:")
            state_info.extend(selection_info)
        else:
            state_info.append("\nNo selections defined.")
            
        state_info.append("\n" + view_str)
        
        logger.info("Successfully retrieved PyMOL session state")
        return "\n".join(state_info)
    except Exception as e:
        logger.error(f"Error retrieving PyMOL state: {str(e)}")
        logger.error(traceback.format_exc())
        return f"Error retrieving PyMOL state: {str(e)}"

# Run the server
if __name__ == "__main__":
    mcp.run()