from typing import List, Literal

def required_macro_categories(
    mode: Literal["stock", "macro", "mixed"], 
    themes: List[str], 
    target_symbols: List[str]
) -> List[str]:
    """
    Centralize macro data requirement rules.
    """
    base_requirements = ["inflation", "rates"]
    
    if mode == "macro":
        base_requirements.extend(["commodity", "fx"])
        
    for theme in themes:
        theme_lower = theme.lower()
        if "energy" in theme_lower or "oil" in theme_lower:
            if "energy" not in base_requirements:
                base_requirements.append("energy")
        if "tech" in theme_lower:
            if "equity" not in base_requirements:
                base_requirements.append("equity")
                
    return list(set(base_requirements))
