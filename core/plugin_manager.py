"""
Dynamic plugin system for extensible models, brokers, and data providers
"""

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Dict, Type, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


class PluginManager:
    """Manages dynamic loading of custom plugins"""
    
    def __init__(self, plugin_dir: Path):
        self.plugin_dir = plugin_dir
        self.loaded_plugins: Dict[str, Any] = {}
        self.plugin_classes: Dict[str, Type] = {}
        
    def load_plugin(self, plugin_path: Path) -> Optional[Any]:
        """Load a single plugin from file"""
        try:
            spec = importlib.util.spec_from_file_location(
                plugin_path.stem, 
                plugin_path
            )
            if spec is None or spec.loader is None:
                logger.error(f"Failed to load spec for {plugin_path}")
                return None
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[plugin_path.stem] = module
            spec.loader.exec_module(module)
            
            self.loaded_plugins[plugin_path.stem] = module
            logger.info(f"Loaded plugin: {plugin_path.stem}")
            return module
            
        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_path}: {e}")
            return None
    
    def load_plugins_from_directory(self, directory: Path) -> List[Type]:
        """Load all plugins from a directory"""
        plugin_classes = []
        
        if not directory.exists():
            logger.warning(f"Plugin directory does not exist: {directory}")
            return plugin_classes
        
        for plugin_file in directory.glob("*.py"):
            if plugin_file.name.startswith("_"):
                continue
                
            module = self.load_plugin(plugin_file)
            if module:
                # Extract plugin classes (classes ending with 'Plugin' or 'Provider')
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        (attr_name.endswith('Plugin') or attr_name.endswith('Provider')) and
                        attr_name != 'BasePlugin'):
                        self.plugin_classes[attr_name] = attr
                        plugin_classes.append(attr)
                        logger.info(f"Registered plugin class: {attr_name}")
        
        return plugin_classes
    
    def load_all_plugins(self) -> None:
        """Load all plugins from configured directories"""
        # Load model plugins
        models_dir = self.plugin_dir / "models"
        self.load_plugins_from_directory(models_dir)
        
        # Load broker plugins
        brokers_dir = self.plugin_dir / "brokers"
        self.load_plugins_from_directory(brokers_dir)
        
        # Load data provider plugins
        data_dir = self.plugin_dir / "data"
        self.load_plugins_from_directory(data_dir)
    
    def get_plugin_class(self, class_name: str) -> Optional[Type]:
        """Get a loaded plugin class by name"""
        return self.plugin_classes.get(class_name)
    
    def reload_plugin(self, plugin_name: str) -> Optional[Any]:
        """Hot-reload a plugin"""
        if plugin_name in self.loaded_plugins:
            module = self.loaded_plugins[plugin_name]
            importlib.reload(module)
            logger.info(f"Reloaded plugin: {plugin_name}")
            return module
        return None
    
    def list_plugins(self) -> Dict[str, List[str]]:
        """List all loaded plugins by category"""
        plugins = {
            "models": [],
            "brokers": [],
            "data": []
        }
        
        for class_name in self.plugin_classes.keys():
            if "model" in class_name.lower() or "llm" in class_name.lower():
                plugins["models"].append(class_name)
            elif "broker" in class_name.lower() or "adapter" in class_name.lower():
                plugins["brokers"].append(class_name)
            elif "data" in class_name.lower() or "provider" in class_name.lower():
                plugins["data"].append(class_name)
        
        return plugins


class BasePlugin:
    """Base class for all plugins"""
    
    plugin_name: str = ""
    plugin_version: str = "1.0.0"
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    def initialize(self) -> bool:
        """Initialize the plugin"""
        return True
    
    def shutdown(self) -> None:
        """Cleanup when plugin is unloaded"""
        pass
    
    @classmethod
    def get_info(cls) -> Dict[str, str]:
        """Get plugin information"""
        return {
            "name": cls.plugin_name,
            "version": cls.plugin_version
        }
