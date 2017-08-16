

class ErrorManager(object):
    """Manage all detect errors"""
    def __init__(self,):
        super().__init__()

        # errors is a map like this
        # {'file_name.purs': [(region1, error1), (region2, error2), ...]}
        self.errors = {}

    # regions_and_errors :: Array (Tuple Region Error)
    # I want type :(
    def set_errors(self, file_name, regions_and_errors):
        self.errors[file_name] = regions_and_errors

    def get_error_at_point(self, file_name, point):
        things = self.errors.get(file_name, [])
        for region, error in things:
            if region.contains(point):
                return error
        return None

error_manager = ErrorManager()
