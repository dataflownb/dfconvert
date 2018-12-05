def _jupyter_bundlerextension_paths():
    """Declare bundler extensions provided by this package."""
    return [
    {
        # unique bundler name
        "name": "dfexport",
        # module containing bundle function
        "module_name": "dfconvert.make_ipy",
        # human-redable menu item label
        "label": "IPyKernel Compatible Notebook",
        # group under 'deploy' or 'download' menu
        "group": "download",
    }
    ]