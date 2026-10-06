"""Write the MCP request files that author BP_S3SackFollower with the MCPBlueprintsGenerator toolset (plain Python,
runs OUTSIDE Unreal). The specs are s3_sack_follower_bp_spec_create.json and s3_sack_follower_bp_spec_ucs_patch.json.

    python Saved/CodexConductor/s3_sack_follower_bp_make_requests.py [--fingerprint <StateFingerprint from Inspect>]

Order (each through Saved/CodexMocap/mcp_request.py tools/call --params-file <file>):
  1 ..._validate_create_request.json   ValidateSpecification (new asset, empty fingerprint)
  2 ..._apply_create_request.json      ApplySpecification, bSaveChanges true -> creates /Game/.../Sack/BP_S3SackFollower
  3 ..._inspect_request.json           InspectBlueprint -> copy its stateFingerprint, re-run this script with it
  4 ..._validate_ucs_request.json      ValidateSpecification of the construction-script patch
  5 ..._apply_ucs_request.json         ApplySpecification (fingerprint-guarded), bSaveChanges true
  6 ..._compile_request.json           CompileBlueprint, bSaveChanges true
Then s3_sack_install.py DRY must report sack_bp OK.
"""
import argparse
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLSET = "MCPBlueprintsGenerator.MCPBlueprintsGeneratorToolset"
BP_OBJECT = "/Game/Metahuman/ShoreCast_20260910/Sack/BP_S3SackFollower.BP_S3SackFollower"
PREFIX = "s3_sack_follower_bp_"


def spec_text(name):
    with open(os.path.join(HERE, PREFIX + name + ".json"), encoding="utf-8") as h:
        return json.dumps(json.load(h), separators=(",", ":"))


def request(tool, arguments):
    return {"name": "call_tool", "arguments": {"toolset_name": TOOLSET, "tool_name": tool, "arguments": arguments}}


def build(fingerprint=""):
    create, patch = spec_text("spec_create"), spec_text("spec_ucs_patch")
    return {
        "validate_create": request("ValidateSpecification", {"specificationJson": create, "expectedTargetFingerprint": ""}),
        "apply_create": request("ApplySpecification", {"specificationJson": create, "expectedTargetFingerprint": "",
                                                       "bSaveChanges": True}),
        "inspect": request("InspectBlueprint", {"assetPath": BP_OBJECT}),
        "validate_ucs": request("ValidateSpecification", {"specificationJson": patch,
                                                          "expectedTargetFingerprint": fingerprint}),
        "apply_ucs": request("ApplySpecification", {"specificationJson": patch, "expectedTargetFingerprint": fingerprint,
                                                    "bSaveChanges": True}),
        "compile": request("CompileBlueprint", {"assetPath": BP_OBJECT, "bSaveChanges": True}),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fingerprint", default="")
    a = p.parse_args()
    for key, body in build(a.fingerprint).items():
        path = os.path.join(HERE, PREFIX + key + "_request.json")
        with open(path, "w", encoding="utf-8", newline="\n") as h:
            json.dump(body, h, separators=(",", ":"))
        print(path)
    if not a.fingerprint:
        print("NOTE: the ucs requests carry an EMPTY fingerprint (check disabled); re-run with --fingerprint after Inspect")


if __name__ == "__main__":
    main()
