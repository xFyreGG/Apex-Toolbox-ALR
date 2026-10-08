"""Human-readable texture reports; deliberately independent of Blender."""

from . import resolver


def texture_report(batch, definition, outcomes=None):
    outcomes = outcomes or {}
    applied = sum(value == "Textured successfully." for value in outcomes.values())
    summary = "%d textured; %d left untouched" % (applied, len(batch.materials) - applied)
    lines = ["APEX TOOLBOX | Auto Texture", "", summary,
             "Shader: " + definition.group_name]
    lines.extend(["", "SEARCH FOLDERS"])
    for root in batch.roots:
        lines.append("%s [%s%s]" % (root.path, root.origin,
                                    "; includes subfolders" if root.recursive else ""))
    if not batch.roots:
        lines.append("No search folder found. Set Texture Folder in Search Options.")
    if batch.index is not None:
        lines.append("%d candidate images indexed." % len(batch.index))
        lines.extend("Search warning: " + warning for warning in batch.index.warnings)
    lines.extend(["", "MATERIALS",
                  "Unresolved optional maps are normal; only referenced missing files block conversion.",
                  "Shared materials are updated for every object that uses them."])
    for material, info in zip(batch.materials, batch.infos):
        results = batch.results.get(material.name, {})
        lines.extend(["", material.name, "  Source: " + info.source_label])
        if material.name in outcomes:
            lines.append("  " + outcomes[material.name])
        if not getattr(material, "is_editable", True):
            lines.append("  Read-only linked material: make it local before applying.")
        for line in resolver.format_report(material.name, info.source_label, results,
                                           order=definition.wanted_roles, prefix="")[2:]:
            lines.append(" " + line)
        for result in results.values():
            if result.resolved and result.path:
                lines.append("    %s: %s" % (result.role, result.path))
        if any(r.status == resolver.STATUS_MISSING for r in results.values()):
            lines.append("  Next: Repair Missing Textures, or re-export with Export Material Textures enabled.")
        elif not any(r.resolved for r in results.values()):
            lines.append("  Next: choose the model's texture folder, enable subfolders if needed, then run Texture Model again.")
    return summary, "\n".join(lines) + "\n"
