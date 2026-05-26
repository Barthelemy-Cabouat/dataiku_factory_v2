"""
Code and recipe development tools for Dataiku MCP integration.
"""

import ast
import re
import json
import tempfile
import traceback
from typing import Dict, Any, List, Optional
from dataiku_mcp.client import get_client, get_project
from dataiku_mcp.tools.api_helpers import recipe_io

def get_recipe_code(
    project_key: str,
    recipe_name: str
) -> Dict[str, Any]:
    """
    Extract actual Python/SQL code from recipes.
    
    Args:
        project_key: The project key
        recipe_name: Name of the recipe
        
    Returns:
        Dict containing code and recipe information
    """
    try:
        project = get_project(project_key)
        recipe = project.get_recipe(recipe_name)
        settings = recipe.get_settings()
        
        # Get recipe metadata via definition-and-payload (works for all recipe types incl. sql_query)
        try:
            def_and_payload = recipe.get_definition_and_payload()
            recipe_type = def_and_payload.type
            inputs = def_and_payload.get_flat_input_refs()
            outputs = def_and_payload.get_flat_output_refs()
        except Exception:
            def_and_payload = None
            recipe_type = "unknown"
            inputs = []
            outputs = []
        
        recipe_info = {
            "name": recipe_name,
            "type": recipe_type,
            "engine": settings.get_recipe_params().get("engine", "unknown"),
            "inputs": inputs,
            "outputs": outputs
        }
        
        # Extract code based on recipe type
        code = ""
        code_info = {}
        
        if recipe_type in ["python", "r", "scala"]:
            # Code recipes
            code = settings.get_code()
            code_info = {
                "language": recipe_type,
                "line_count": len(code.split('\n')) if code else 0,
                "char_count": len(code) if code else 0
            }
            
        elif recipe_type in ["sql", "sql_query", "sparksql", "hive"]:
            # SQL query recipes store the query as the payload
            code = ''
            if def_and_payload is not None:
                raw = def_and_payload.get_payload()
                code = raw if isinstance(raw, str) else ''
            if not code and hasattr(settings, 'get_code'):
                try:
                    code = settings.get_code() or ''
                except Exception:
                    code = ''
            code_info = {
                "language": "sql",
                "line_count": len(code.split('\n')) if code else 0,
                "char_count": len(code) if code else 0
            }
            
        elif recipe_type == "pyspark":
            # PySpark recipes
            code = settings.get_code()
            code_info = {
                "language": "python",
                "engine": "pyspark",
                "line_count": len(code.split('\n')) if code else 0,
                "char_count": len(code) if code else 0
            }
            
        elif recipe_type in ["join", "grouping", "window", "distinct", "sort", "topn", "sync"]:
            # Visual recipes - extract configuration as "pseudo-code"
            recipe_params = settings.get_recipe_params()
            code = json.dumps(recipe_params, indent=2)
            code_info = {
                "language": "json",
                "type": "visual_recipe_config",
                "line_count": len(code.split('\n')) if code else 0,
                "char_count": len(code) if code else 0
            }
            
        else:
            # Other recipe types
            try:
                code = settings.get_code()
                code_info = {
                    "language": "unknown",
                    "line_count": len(code.split('\n')) if code else 0,
                    "char_count": len(code) if code else 0
                }
            except:
                # For recipes without code, get the configuration
                recipe_params = settings.get_recipe_params()
                code = json.dumps(recipe_params, indent=2)
                code_info = {
                    "language": "json",
                    "type": "recipe_config",
                    "line_count": len(code.split('\n')) if code else 0,
                    "char_count": len(code) if code else 0
                }
        
        return {
            "status": "ok",
            "recipe_info": recipe_info,
            "code": code,
            "code_info": code_info
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get recipe code for '{recipe_name}': {str(e)}"
        }


def validate_recipe_syntax(
    project_key: str,
    recipe_name: str,
    code: Optional[str] = None
) -> Dict[str, Any]:
    """
    Validate Python/SQL syntax before execution.
    
    Args:
        project_key: The project key
        recipe_name: Name of the recipe
        code: Optional code to validate (if not provided, gets from recipe)
        
    Returns:
        Dict containing validation results
    """
    try:
        project = get_project(project_key)
        recipe = project.get_recipe(recipe_name)
        
        # Get code to validate
        def_and_payload = recipe.get_definition_and_payload()
        recipe_type = def_and_payload.type
        if code is None:
            if recipe_type in ["sql", "sql_query", "sparksql", "hive"]:
                raw = def_and_payload.get_payload()
                code = raw if isinstance(raw, str) else ''
            else:
                settings = recipe.get_settings()
                try:
                    code = settings.get_code() or ''
                except Exception:
                    code = ''

        if not code or not code.strip():
            return {
                "status": "ok",
                "valid": True,
                "message": "No code to validate (empty recipe)",
                "errors": []
            }
        validation_results = {
            "recipe_name": recipe_name,
            "recipe_type": recipe_type,
            "code_length": len(code),
            "line_count": len(code.split('\n'))
        }
        
        errors = []
        warnings = []
        
        # Validate based on recipe type
        if recipe_type in ["python", "pyspark"]:
            # Python syntax validation
            try:
                ast.parse(code)
                validation_results["python_ast_valid"] = True
            except SyntaxError as e:
                errors.append({
                    "type": "syntax_error",
                    "line": e.lineno,
                    "column": e.offset,
                    "message": str(e.msg),
                    "text": e.text.strip() if e.text else ""
                })
                validation_results["python_ast_valid"] = False
            except Exception as e:
                errors.append({
                    "type": "parse_error",
                    "message": f"Failed to parse Python code: {str(e)}"
                })
                validation_results["python_ast_valid"] = False
            
            # Check for common Dataiku patterns
            if "dataiku" not in code.lower():
                warnings.append({
                    "type": "missing_dataiku_import",
                    "message": "Code doesn't seem to import dataiku package"
                })
            
            # Check for input/output dataset handling
            if "get_dataframe" not in code and "iter_rows" not in code:
                warnings.append({
                    "type": "no_input_handling",
                    "message": "Code doesn't seem to handle input datasets"
                })
            
            if "write_with_schema" not in code and "write_dataframe" not in code:
                warnings.append({
                    "type": "no_output_handling",
                    "message": "Code doesn't seem to write to output datasets"
                })
                
        elif recipe_type == "sql":
            # SQL syntax validation (basic)
            sql_errors = []
            
            # Basic SQL syntax checks
            if not re.search(r'\bSELECT\b', code, re.IGNORECASE):
                sql_errors.append({
                    "type": "missing_select",
                    "message": "SQL code should contain a SELECT statement"
                })
            
            # Check for balanced parentheses
            if code.count('(') != code.count(')'):
                sql_errors.append({
                    "type": "unbalanced_parentheses",
                    "message": "Unbalanced parentheses in SQL code"
                })
            
            # Check for unterminated strings
            single_quotes = code.count("'") - code.count("\\'")
            double_quotes = code.count('"') - code.count('\\"')
            
            if single_quotes % 2 != 0:
                sql_errors.append({
                    "type": "unterminated_string",
                    "message": "Unterminated single-quoted string"
                })
            
            if double_quotes % 2 != 0:
                sql_errors.append({
                    "type": "unterminated_string",
                    "message": "Unterminated double-quoted string"
                })
            
            errors.extend(sql_errors)
            validation_results["sql_basic_valid"] = len(sql_errors) == 0
            
        elif recipe_type == "r":
            # R syntax validation (basic)
            r_errors = []
            
            # Check for balanced parentheses and brackets
            if code.count('(') != code.count(')'):
                r_errors.append({
                    "type": "unbalanced_parentheses",
                    "message": "Unbalanced parentheses in R code"
                })
            
            if code.count('[') != code.count(']'):
                r_errors.append({
                    "type": "unbalanced_brackets",
                    "message": "Unbalanced brackets in R code"
                })
            
            if code.count('{') != code.count('}'):
                r_errors.append({
                    "type": "unbalanced_braces",
                    "message": "Unbalanced braces in R code"
                })
            
            errors.extend(r_errors)
            validation_results["r_basic_valid"] = len(r_errors) == 0
            
        else:
            # For other recipe types, just check if it's valid JSON (for visual recipes)
            try:
                json.loads(code)
                validation_results["json_valid"] = True
            except json.JSONDecodeError as e:
                validation_results["json_valid"] = False
                # This might not be JSON, which is fine for some recipe types
        
        # Overall validation result
        is_valid = len(errors) == 0
        
        return {
            "status": "ok",
            "valid": is_valid,
            "validation_results": validation_results,
            "errors": errors,
            "warnings": warnings,
            "error_count": len(errors),
            "warning_count": len(warnings)
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to validate recipe syntax: {str(e)}"
        }


def test_recipe_dry_run(
    project_key: str,
    recipe_name: str,
    sample_rows: int = 100
) -> Dict[str, Any]:
    """
    Test recipe logic without actual execution.
    
    Args:
        project_key: The project key
        recipe_name: Name of the recipe
        sample_rows: Number of sample rows to test with
        
    Returns:
        Dict containing test results
    """
    try:
        project = get_project(project_key)
        recipe = project.get_recipe(recipe_name)
        settings = recipe.get_settings()
        
        # Get recipe information
        try:
            def_and_payload = recipe.get_definition_and_payload()
            refs = recipe_io(recipe)
            inputs = refs["inputs"]
            outputs = refs["outputs"]
            recipe_type = def_and_payload.type
        except Exception:
            try:
                recipe_def_payload = recipe.get_definition_and_payload()
                recipe_type = recipe_def_payload.type
                inputs = []
                outputs = []
            except Exception:
                recipe_type = "unknown"
                inputs = []
                outputs = []
        test_results = {
            "recipe_name": recipe_name,
            "recipe_type": recipe_type,
            "inputs": inputs,
            "outputs": outputs,
            "sample_rows": sample_rows
        }
        
        # Check if inputs exist and are accessible
        input_checks = []
        for input_name in inputs:
            try:
                input_dataset = project.get_dataset(input_name)
                schema = input_dataset.get_schema()
                
                # Try to get sample data
                try:
                    import itertools
                    sample_rows_list = list(itertools.islice(input_dataset.iter_rows(), sample_rows))
                    input_info = {
                        "name": input_name,
                        "status": "ok",
                        "schema_columns": len(schema["columns"]),
                        "sample_rows": len(sample_rows_list),
                        "sample_columns": [col.get("name") for col in schema.get("columns", [])]
                    }
                except Exception as e:
                    input_info = {
                        "name": input_name,
                        "status": "warning",
                        "message": f"Could not read sample data: {str(e)}",
                        "schema_columns": len(schema["columns"]) if schema else 0
                    }
                
                input_checks.append(input_info)
                
            except Exception as e:
                input_checks.append({
                    "name": input_name,
                    "status": "error",
                    "message": f"Input dataset not accessible: {str(e)}"
                })
        
        test_results["input_checks"] = input_checks
        
        # Check if outputs are properly configured
        output_checks = []
        for output_name in outputs:
            try:
                output_dataset = project.get_dataset(output_name)
                output_info = {
                    "name": output_name,
                    "status": "ok",
                    "exists": True,
                    "type": output_dataset.get_settings().get_raw()["type"]
                }
            except Exception as e:
                output_info = {
                    "name": output_name,
                    "status": "warning",
                    "exists": False,
                    "message": f"Output dataset will be created: {str(e)}"
                }
            
            output_checks.append(output_info)
        
        test_results["output_checks"] = output_checks
        
        # For Python recipes, try to validate the code structure
        if recipe_type in ["python", "pyspark"]:
            try:
                code = settings.get_code()
                
                # Parse the code to check for basic structure
                tree = ast.parse(code)
                
                # Check for dataiku imports
                has_dataiku_import = False
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name == "dataiku":
                                has_dataiku_import = True
                    elif isinstance(node, ast.ImportFrom):
                        if node.module == "dataiku":
                            has_dataiku_import = True
                
                # Check for dataset operations
                has_input_read = "get_dataframe" in code or "iter_rows" in code
                has_output_write = "write_with_schema" in code or "write_dataframe" in code
                
                code_analysis = {
                    "has_dataiku_import": has_dataiku_import,
                    "has_input_read": has_input_read,
                    "has_output_write": has_output_write,
                    "line_count": len(code.split('\n')),
                    "ast_valid": True
                }
                
                test_results["code_analysis"] = code_analysis
                
            except Exception as e:
                test_results["code_analysis"] = {
                    "ast_valid": False,
                    "error": str(e)
                }
        
        # Generate test summary
        input_errors = sum(1 for check in input_checks if check["status"] == "error")
        output_errors = sum(1 for check in output_checks if check["status"] == "error")
        
        test_summary = {
            "overall_status": "ok" if input_errors == 0 and output_errors == 0 else "warning",
            "input_errors": input_errors,
            "output_errors": output_errors,
            "ready_for_execution": input_errors == 0,
            "recommendations": []
        }
        
        # Add recommendations
        if input_errors > 0:
            test_summary["recommendations"].append("Fix input dataset access issues before running")
        
        if recipe_type in ["python", "pyspark"]:
            code_analysis = test_results.get("code_analysis", {})
            if not code_analysis.get("has_dataiku_import", False):
                test_summary["recommendations"].append("Add 'import dataiku' to your code")
            if not code_analysis.get("has_input_read", False):
                test_summary["recommendations"].append("Add code to read input datasets")
            if not code_analysis.get("has_output_write", False):
                test_summary["recommendations"].append("Add code to write output datasets")
        
        test_results["test_summary"] = test_summary
        
        return {
            "status": "ok",
            "test_results": test_results
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to perform dry run test: {str(e)}"
        }
