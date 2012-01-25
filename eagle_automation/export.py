from eagle_automation.config import *
import os
import subprocess
import tempfile

class BadExtension: Exception

class EagleScriptExport:
	def __init__(self, workdir=None):
		self.workdir = workdir

	def export(self, in_path, layers, out_paths):

		open(in_path, "rb").close()

		workdir = self.workdir or tempfile.mkdtemp()

		script_path = os.path.join(workdir, "export.scr")
		script = open(script_path, "w")

		extension = in_path.split('.')[-1].lower()

		self.write_script(script, extension, layers, out_paths)

		script.close()

		for out_path in out_paths:
			# to stop Eagle trowing up dialogs that
			# files already exist
			try:
				os.unlink(out_path)
			except OSError:
				pass

		cmd = [EAGLE, "-S" + script_path, in_path]
		subprocess.call(cmd)

		os.unlink(script_path)

		if not self.workdir:
			os.rmdir(workdir)

class EaglePNGExport(EagleScriptExport):
	def write_script(self, script, extension, layers, out_paths):

		if extension == 'brd':
			script.write("BRD:\nDISPLAY ALL\nRATSNEST\n")
		elif extension == 'sch':
			script.write("SCH:\n")
		else:
			raise BadExtension

		for layer, out_path in zip(layers, out_paths):
			assert out_path.endswith(".png")

			script.write("DISPLAY None\n")
			script.write("DISPLAY %s\n" % (' '.join(layer['layers']),))
			script.write("EXPORT IMAGE %s MONOCHROME %d\n" % (out_path, DPI))

		script.write("QUIT\n")

class EaglePDFExport(EagleScriptExport):
	def write_script(self, script, extension, layers, out_paths):

		if extension == 'brd':
			script.write("BRD:\nDISPLAY ALL\nRATSNEST\n")
		else:
			raise BadExtension

		for layer, out_path in zip(layers, out_paths):

			ll = set(layer['layers']) | set(DOCUMENT_LAYERS)
			script.write("DISPLAY None\n")
			script.write("DISPLAY %s\n" % (' '.join(ll),))
			script.write("PRINT FILE %s BLACK SOLID ;\n" % (out_path,))

		script.write("QUIT\n")

class EagleCAMExport:
	def __init__(self, workdir=None):
		pass

	def export(self, in_path, layers, out_paths):

		open(in_path, "rb").close()

		extension = in_path.split('.')[-1].lower()
		if extension != 'brd':
			raise BadExtension

		for layer, out_path in zip(layers, out_paths):
			options = ["-X", "-d" + self.DEVICE, "-o"  + out_path]
			if layer.get('mirror'):
				options.append("-m")
			cmd = [EAGLE] + options + [in_path] + layer['layers']
			subprocess.call(cmd)

class EagleGerberExport(EagleCAMExport):
	DEVICE = "GERBER_RS274X"

class EagleExcellonExport(EagleCAMExport):
	DEVICE = "EXCELLON"
