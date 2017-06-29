def _jupyter_bundlerextension_paths():
    """Declare bundler extensions provided by this package."""
    return [{
        # unique bundler name
        "name": "dfipy_import",
        # module containing bundle function
        "module_name": "dfipy_convert.import",
        # human-redable menu item label
        "label" : "Dataflow Compatible Notebook",
        # group under 'deploy' or 'download' menu
        "group" : "download",
    },
    {
        # unique bundler name
        "name": "dfipy_export",
        # module containing bundle function
        "module_name": "dfipy_convert.export",
        # human-redable menu item label
        "label": "IPyKernel Compatible Notebook",
        # group under 'deploy' or 'download' menu
        "group": "download",
    }
    ]