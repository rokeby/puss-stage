def main():
    import unreal
    for n in dir(unreal):
        if "MaterialParameterSection" in n or n == "MovieSceneComponentMaterialParameterSection":
            c = getattr(unreal, n)
            f = getattr(c, "add_scalar_parameter_key", None)
            unreal.log("PARAM_SIG|%s|%s" % (n, ((f.__doc__ or "") if f else "none")[:500].replace("\n", " / ")))
main()
