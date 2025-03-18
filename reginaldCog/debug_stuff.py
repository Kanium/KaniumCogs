def debug(func):
    def wrap(*args, **kwargs):
        # Log the function name and arguments
        print(f"DEBUG: Calling {func.__name__} with args: {args}, kwargs: {kwargs}")

        # Call the original function
        result = func(*args, **kwargs)

        # Log the return value
        print(f"DEBUG: {func.__name__} returned: {result}")

        # Return the result
        return result

    return wrap
