LAYERS = {
	'topsilk': {
		'layers': ['tPlace', 'tNames'],
	},
	
	'toppaste': {
		'layers': ['tCream'],
	},

	'topmask': {
		'layers': ['tStop'],
	},

	'topcopper': {
		'layers': ['Top', 'Pads', 'Vias'],
	},

	'bottomcopper': {
		'layers': ['Bottom', 'Pads', 'Vias'],
		'mirror': True,
	},

	'bottommask': {
		'layers': ['bStop'],
		'mirror': True,
	},
	
	'bottompaste': {
		'layers': ['bCream'],
		'mirror': True,
	},

	'bottomsilk': {
		'layers': ['bPlace', 'bNames'],
		'mirror': True,
	},

	'measures': {
		'layers': ['LayerStackup', 'DrillLegend', 'Measures'],
	},

	'drills': {
		'layers': ['Drills', 'Holes'],
	},
}

DOCUMENT_LAYERS = ['Dimension', 'Document']

EAGLE = "eagle"

DPI = 400
