import os
import shutil
import tempfile
from contextlib import contextmanager


@contextmanager
def local_file(file_field):
    try:
        path = file_field.path
        is_temp = False
    except NotImplementedError:
        suffix = os.path.splitext(file_field.name)[1]
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        with file_field.open("rb") as src:
            shutil.copyfileobj(src, tmp)
        tmp.close()
        path = tmp.name
        is_temp = True
    try:
        yield path
    finally:
        if is_temp:
            try:
                os.unlink(path)
            except OSError:
                pass
