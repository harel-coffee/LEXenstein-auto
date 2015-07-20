from lexenstein.util import getGeneralisedPOS
from nltk.stem.porter import *
from nltk.corpus import wordnet as wn
import kenlm
import math
import gensim
from nltk.tag.stanford import StanfordPOSTagger
import os
import pickle
from sklearn.preprocessing import normalize
import numpy
import shelve

class FeatureEstimator:

	def __init__(self, norm=False):
		"""
		Creates an instance of the FeatureEstimator class.
	
		@param norm: Boolean variable that determines whether or not feature values should be normalized.
		"""
		#List of features to be calculated:
		self.features = []
		#List of identifiers of features to be calculated:
		self.identifiers = []
		#Normalization parameter:
		self.norm = norm
		#Persistent resource list:
		self.resources = {}
		#One-run resource list:
		self.temp_resources = {}
		
	def calculateFeatures(self, corpus, format='victor'):
		"""
		Calculate the selected features over the candidates of a VICTOR or CWICTOR corpus.
	
		@param corpus: Path to a corpus in the VICTOR or CWICTOR format.
		For more information about the file's format, refer to the LEXenstein Manual.
		@param format: Input file format.
		Values available: victor, cwictor
		@return: Returns a MxN matrix, where M is the number of substitutions of all instances in the VICTOR corpus, and N the number of selected features.
		"""
		
		data = []
		if format.strip().lower()=='victor':
			data = [line.strip().split('\t') for line in open(corpus)]
		elif format.strip().lower()=='cwictor':
			f = open(corpus)
			for line in f:
				line_data = line.strip().split('\t')
				data.append([line_data[0].strip(), line_data[1].strip(), line_data[2].strip(), '0:'+line_data[1].strip()])
		else:
			print('Unknown input format during feature estimation!')
			return []
		
		values = []
		for feature in self.features:
			values.append(feature[0].__call__(data, feature[1]))
			
		result = []
		index = 0
		for line in data:
			for i in range(3, len(line)):
				vector = self.generateVector(values, index)
				result.append(vector)
				index += 1
				
		#Normalize if required:
		if self.norm:
			result = normalize(result, axis=0)
		
		#Clear one-run resources:
		self.temp_resources = {}
		
		return result
		
	def calculateInstanceFeatures(self, sent, target, head, candidate):
		"""
		Calculate the selected features over an instance of a VICTOR corpus.
	
		@param sent: Sentence containing a target complex word.
		@param target: Target complex sentence to be simplified.
		@param head: Position of target complex word in sentence.
		@param candidate: Candidate substitution.
		@return: Returns a vector containing the feature values of VICTOR instance.
		"""
	
		data = [[sent, target, head, '0:'+candidate]]
		
		values = []
		for feature in self.features:
			values.append(feature[0].__call__(data, feature[1]))
		vector = self.generateVector(values, 0)
		return vector
		
	def generateVector(self, feature_vector, index):
		result = []
		for feature in feature_vector:
			if not isinstance(feature[index], list):
				result.append(feature[index])
			else:
				result.extend(feature[index])
		return result
	
	def targetPOSTagProbability(self, data, args):
		model = self.resources[args[0]]
		tagger = self.resources[args[1]]
		result = []
		
		#Get tagged sentences:
		tagged_sents = None
		if 'tagged_sents' in self.temp_resources:
			tagged_sents = self.temp_resources['tagged_sents']
		else:
			sentences = [l[0].strip().split(' ') for l in data]
			tagged_sents = tagger.tag_sents(sentences)
			self.temp_resources['tagged_sents'] = tagged_sents
		
		for i in range(0, len(data)):
			line = data[i]
			target = line[1].strip().lower()
			head = int(line[2].strip())
			target_pos = tagged_sents[i][head][1]
			
			for subst in line[3:len(line)]:
				words = subst.strip().split(':')[1].strip()
				probability = model[words].prob(target_pos)
				result.append(probability)
		return result
	
	def wordVectorSimilarityFeature(self, data, args):
		model = self.resources[args[0]]
		result = []
		for line in data:
			target = line[1].strip().lower()
			for subst in line[3:len(line)]:
				words = subst.strip().split(':')[1].strip()
				similarity = 0.0
				cand_size = 0
				for word in words.split(' '):
					cand_size += 1
					try:
						similarity += model.similarity(target, word)
					except KeyError:
						try:
							similarity += model.similarity(target, word.lower())
						except KeyError:
							pass
				similarity /= cand_size
				result.append(similarity)
		return result
		
	def taggedWordVectorSimilarityFeature(self, data, args):
		result = []
		
		model = self.resources[args[0]]
		tagger = self.resources[args[1]]
		pos_type = args[2]
		
		#Get tagged sentences:
		tagged_sents = None
		if 'tagged_sents' in self.temp_resources:
			tagged_sents = self.temp_resources['tagged_sents']
		else:
			sentences = [l[0].strip().split(' ') for l in data]
			tagged_sents = tagger.tag_sents(sentences)
			self.temp_resources['tagged_sents'] = tagged_sents
			
		#Transform them to the right format:
		if pos_type=='paetzold':
			transformed = []
			for sent in tagged_sents:
				tokens = []
				for token in sent:
					tokens.append((token[0], getGeneralisedPOS(token[1])))
				transformed.append(tokens)
			tagged_sents = transformed

		for i in range(0, len(data)):
			line = data[i]
			target = line[1].strip().lower()
			head = int(line[2].strip())
			target_pos = tagged_sents[i][head][1]
			for subst in line[3:len(line)]:
				words = subst.strip().split(':')[1].strip()
				similarity = 0.0
				cand_size = 0
				for word in words.split(' '):
					cand_size += 1
					try:
						similarity += model.similarity(target+'|||'+target_pos, word+'|||'+target_pos)
					except KeyError:
						try:
							similarity += model.similarity(target+'|||'+target_pos, word.lower()+'|||'+target_pos)
						except KeyError:
							pass
				similarity /= cand_size
				result.append(similarity)
		return result
	
	def wordVectorValuesFeature(self, data, args):
		model = self.resources[args[0]]
		size = args[1]
		result = []
		for line in data:
			target = line[1].strip().lower()
			for subst in line[3:len(line)]:
				words = subst.strip().split(':')[1].strip()
				word_vector = numpy.zeros(size)
				for word in words.split(' '):
					try:
						word_vector = numpy.add(word_vector, model[words])
					except KeyError:
						pass
				result.append(word_vector)
		for i in range(0, len(result)):
			result[i] = result[i].tolist()
		return result
	
	def translationProbabilityFeature(self, data, args):
		probabilities = self.resources[args[0]]
		result = []
		for line in data:
			target_probs = {}
			if line[1].strip() in probabilities.keys():
				target_probs = probabilities[line[1].strip()]
			for subst in line[3:len(line)]:
				words = subst.strip().split(':')[1].strip()
				prob = 1.0
				for word in words.split(' '):
					if word in target_probs.keys():
						prob *= target_probs[word]
					else:
						prob = 0.0
				result.append(prob)
		return result
		
	def lexiconFeature(self, data, args):
		path = args[0]
		result = []
		basics = self.resources[path]
		for line in data:
			for subst in line[3:len(line)]:
				words = subst.strip().split(':')[1].strip()
				basicCount = 0
				for word in words.split(' '):
					if word.strip() in basics:
						basicCount += 1
				if basicCount==len(words.split(' ')):
					result.append(1.0)
				else:
					result.append(0.0)
		return result
		
	def lengthFeature(self, data, args):
		result = []
		for line in data:
			for subst in line[3:len(line)]:
				word = subst.strip().split(':')[1].strip()
				result.append(len(word))
		return result
		
	def syllableFeature(self, data, args):
		mat = args[0]
		#Create the input for the Java application:
		input = []
		for line in data:
			for subst in line[3:len(line)]:
				word = subst.strip().split(':')[1].strip()
				input.append(word)
	
		#Run the syllable splitter:
		outr = mat.splitSyllables(input)

		#Decode output:
		out = []
		for o in outr:
			out.append(o.decode("latin1").replace(' ', '-'))
	
		#Calculate number of syllables
		result = []
		for instance in out:
			if len(instance.strip())>0:
				result.append(len(instance.split('-')))
		return result
	
	def collocationalFeature(self, data, args):
		lm = args[0]
		spanl = args[1]
		spanr = args[2]
		result = []
		model = self.resources[lm]
		for line in data:
			sent = line[0].strip().split(' ')
			target = line[1]
			head = int(line[2])
			spanlv = range(0, spanl+1)
			spanrv = range(0, spanr+1)
			for subst in line[3:len(line)]:
				word = subst.split(':')[1].strip()
				values = []
				for span1 in spanlv:
					for span2 in spanrv:
						ngram, bosv, eosv = self.getNgram(word, sent, head, span1, span2)
						aux = model.score(ngram, bos=bosv, eos=eosv)
						values.append(aux)
				result.append(values)
		return result
		
	def frequencyCollocationalFeature(self, data, args):
		ngrams = args[0]
		spanl = args[1]
		spanr = args[2]
		result = []
		counts = self.resources[ngrams]
		for line in data:
			sent = line[0].strip().split(' ')
			target = line[1]
			head = int(line[2])
			spanlv = range(0, spanl+1)
			spanrv = range(0, spanr+1)
			for subst in line[3:len(line)]:
				word = subst.split(':')[1].strip()
				values = []
				for span1 in spanlv:
					for span2 in spanrv:
						ngram, bosv, eosv = self.getNgram(word, sent, head, span1, span2)
						if ngram in counts:
							values.append(counts[ngram])
						else:
							values.append(0.0)
				result.append(values)
		return result
		
	def taggedFrequencyCollocationalFeature(self, data, args):
		counts = self.resources[args[0]]
		spanl = args[1]
		spanr = args[2]
		tagger = self.resources[args[3]]
		pos_type = args[4]
		
		#Get tagged sentences:
		tagged_sents = None
		if 'tagged_sents' in self.temp_resources:
			tagged_sents = self.temp_resources['tagged_sents']
		else:
			sentences = [l[0].strip().split(' ') for l in data]
			tagged_sents = tagger.tag_sents(sentences)
			self.temp_resources['tagged_sents'] = tagged_sents
			
		#Transform them to the right format:
		if pos_type=='paetzold':
			transformed = []
			for sent in tagged_sents:
				tokens = []
				for token in sent:
					tokens.append((token[0], getGeneralisedPOS(token[1])))
				transformed.append(tokens)
			tagged_sents = transformed
		
		result = []
		for i in range(0, len(data)):
			line = data[i]
			sent = ['<s>'] + [tokendata[1] for tokendata in tagged_sents[i]] + ['</s>']
			target = line[1]
			head = int(line[2])+1
			spanlv = range(0, spanl+1)
			spanrv = range(0, spanr+1)
			for subst in line[3:len(line)]:
				word = subst.split(':')[1].strip()
				values = []
				for span1 in spanlv:
					for span2 in spanrv:
						ngram, bosv, eosv = self.getNgram(word, sent, head, span1, span2)
						if ngram in counts:
							values.append(counts[ngram])
						else:
							values.append(0.0)
				result.append(values)
		return result
		
	def binaryTaggedFrequencyCollocationalFeature(self, data, args):
		counts = self.resources[args[0]]
		spanl = args[1]
		spanr = args[2]
		tagger = self.resources[args[3]]
		pos_type = args[4]
		
		#Get tagged sentences:
		tagged_sents = None
		if 'tagged_sents' in self.temp_resources:
			tagged_sents = self.temp_resources['tagged_sents']
		else:
			sentences = [l[0].strip().split(' ') for l in data]
			tagged_sents = tagger.tag_sents(sentences)
			self.temp_resources['tagged_sents'] = tagged_sents
			
		#Transform them to the right format:
		if pos_type=='paetzold':
			transformed = []
			for sent in tagged_sents:
				tokens = []
				for token in sent:
					tokens.append((token[0], getGeneralisedPOS(token[1])))
				transformed.append(tokens)
			tagged_sents = transformed
		
		result = []
		for i in range(0, len(data)):
			line = data[i]
			sent = ['<s>'] + [tokendata[1] for tokendata in tagged_sents[i]] + ['</s>']
			target = line[1]
			head = int(line[2])+1
			spanlv = range(0, spanl+1)
			spanrv = range(0, spanr+1)
			for subst in line[3:len(line)]:
				word = subst.split(':')[1].strip()
				values = []
				for span1 in spanlv:
					for span2 in spanrv:
						ngram, bosv, eosv = self.getNgram(word, sent, head, span1, span2)
						if ngram in counts:
							values.append(1.0)
						else:
							values.append(0.0)
				result.append(values)
		return result
	
	def popCollocationalFeature(self, data, args):
		lm = args[0]
		spanl = args[1]
		spanr = args[2]
		result = []
		model = self.resources[lm]
		for line in data:
			sent = line[0]
			target = line[1]
			head = int(line[2])
			spanlv = range(0, spanl+1)
			spanrv = range(0, spanr+1)
			for subst in line[3:len(line)]:
				word = subst.split(':')[1].strip()
				values = []
				for span1 in spanlv:
					for span2 in spanrv:
						ngrams = self.getPopNgrams(word, sent, head, span1, span2)
						maxscore = -999999
						for ngram in ngrams:
							aux = model.score(ngram[0], bos=ngram[1], eos=ngram[2])
							if aux>maxscore:
								maxscore = aux
						values.append(maxscore)
				result.append(values)
		return result
		
	def ngramProbabilityFeature(self, data, args):
		lm = args[0]
		spanl = args[1]
		spanr = args[2]
		result = []
		model = self.resources[lm]
		for line in data:
			sent = line[0].strip().split(' ')
			target = line[1]
			head = int(line[2])
			for subst in line[3:len(line)]:
				word = subst.split(':')[1].strip()
				ngram, bosv, eosv = self.getNgram(word, sent, head, spanl, spanr)
				prob = model.score(ngram, bos=bosv, eos=eosv)
				result.append(prob)
		return result
		
	def ngramFrequencyFeature(self, data, args):
		ngrams = args[0]
		spanl = args[1]
		spanr = args[2]
		result = []
		counts = self.resources[ngrams]
		for line in data:
			sent = line[0].strip().split(' ')
			target = line[1]
			head = int(line[2])
			for subst in line[3:len(line)]:
				word = subst.split(':')[1].strip()
				ngram, bosv, eosv = self.getNgram(word, sent, head, spanl, spanr)
				if ngram in counts:
					result.append(counts[ngram])
				else:
					result.append(0.0)
		return result
		
	def binaryNgramFrequencyFeature(self, data, args):
		ngrams = args[0]
		spanl = args[1]
		spanr = args[2]
		result = []
		counts = self.resources[ngrams]
		for line in data:
			sent = line[0].strip().split(' ')
			target = line[1]
			head = int(line[2])
			for subst in line[3:len(line)]:
				word = subst.split(':')[1].strip()
				ngram, bosv, eosv = self.getNgram(word, sent, head, spanl, spanr)
				if ngram in counts:
					result.append(1.0)
				else:
					result.append(0.0)
		return result
		
	def popNgramProbabilityFeature(self, data, args):
		lm = args[0]
		spanl = args[1]
		spanr = args[2]
		result = []
		model = self.resources[lm]
		for line in data:
			sent = line[0]
			target = line[1]
			head = int(line[2])
			for subst in line[3:len(line)]:
				word = subst.split(':')[1].strip()
				ngrams = self.getPopNgrams(word, sent, head, spanl, spanl)
				maxscore = -999999
				for ngram in ngrams:
					aux = model.score(ngram[0], bos=ngram[1], eos=ngram[2])
					if aux>maxscore:
						maxscore = aux
				result.append(maxscore)
		return result
	
	def getNgram(self, cand, tokens, head, configl, configr):
		if configl==0 and configr==0:
			return cand, False, False
		else:
			result = ''
			bosv = False
			if max(0, head-configl)==0:
				bosv = True
			eosv = False
			if min(len(tokens), head+configr+1)==len(tokens):
				eosv = True
			for i in range(max(0, head-configl), head):
				result += tokens[i] + ' '
			result += cand + ' '
			for i in range(head+1, min(len(tokens), head+configr+1)):
				result += tokens[i] + ' '
			return str(result.strip()), bosv, eosv
	
	def getPopNgrams(self, cand, sent, head, configl, configr):
		if configl==0 and configr==0:
			bos = False
			eos = False
			if head==0:
				bos = True
			if head==len(sent.split(' '))-1:
				eos = True
			return [(cand, bos, eos)]
		else:
			result = set([])
			contexts = self.getPopContexts(sent, head)
			for context in contexts:
				ctokens = context[0]
				chead = context[1]
				bosv = False
				if max(0, chead-configl)==0:
					bosv = True
				eosv = False
				ngram = ''
				if min(len(ctokens), chead+configr+1)==len(ctokens):
					eosv = True
				for i in range(max(0, chead-configl), chead):
					ngram += ctokens[i] + ' '
				ngram += cand + ' '
				for i in range(chead+1, min(len(ctokens), chead+configr+1)):
					ngram += ctokens[i] + ' '
				result.add((ngram, bosv, eosv))
			return result
			
	def getPopContexts(self, sent, head):
		tokens = sent.strip().split(' ')
		result = []
		check = 0
		if head>0:
			check += 1
			tokens1 = list(tokens)
			tokens1.pop(head-1)
			result.append((tokens1, head-1))
		if head<len(tokens)-1:
			check += 1
			tokens2 = list(tokens)
			tokens2.pop(head+1)
			result.append((tokens2, head))
		if check==2:
			tokens3 = list(tokens)
			tokens3.pop(head+1)
			tokens3.pop(head-1)
			result.append((tokens3, head-1))
		return result
			
	def sentenceProbabilityFeature(self, data, args):
		lm = args[0]
		result = []
		model = self.resources[lm]
		for line in data:
			sent = line[0].strip().split(' ')
			target = line[1]
			head = int(line[2])
			for subst in line[3:len(line)]:
				word = subst.split(':')[1].strip()
				ngram, bosv, eosv = self.getNgram(word, sent, head, 9999, 9999)
				aux = -1.0*model.score(ngram, bos=bosv, eos=eosv)
				result.append(aux)
		return result
		
	def senseCount(self, data, args):
		resultse = []
		for line in data:
			for subst in line[3:len(line)]:
				words = subst.strip().split(':')[1].strip()
				sensec = 0
				for word in words.split(' '):
					senses = None
					try:
						senses = wn.synsets(word)
					except UnicodeDecodeError:
						senses = []
					sensec += len(senses)
				resultse.append(sensec)
		return resultse
	
	def synonymCount(self, data, args):
		resultsy = []
		for line in data:
			for subst in line[3:len(line)]:
				words = subst.strip().split(':')[1].strip()
				syncount = 0
				for word in words.split(' '):
					senses = None
					try:
						senses = wn.synsets(word)
					except UnicodeDecodeError:
						senses = []
					for sense in senses:
						syncount += len(sense.lemmas())
				resultsy.append(syncount)
		return resultsy
		
	def isSynonym(self, data, args):
		resultsy = []
		for line in data:
			target = line[1].strip()
			tgtsenses = set([])
			try:
				tgtsenses = wn.synsets(target)
			except Exception:
				tgtsenses = set([])
			for subst in line[3:len(line)]:
				words = subst.strip().split(':')[1].strip()
				senses = set([])
				for word in words.split(' '):
					try:
						senses.update(wn.synsets(word))
					except UnicodeDecodeError:
						senses = senses
				if len(tgtsenses)==0 or len(senses.intersection(tgtsenses))>0:
					resultsy.append(1.0)
				else:
					resultsy.append(0.0)
		return resultsy

	def hypernymCount(self, data, args):
		resulthe = []
		for line in data:
			for subst in line[3:len(line)]:
				words = subst.strip().split(':')[1].strip()
				hypernyms = set([])
				for word in words.split(' '):
					senses = None
					try:
						senses = wn.synsets(word)
					except UnicodeDecodeError:
						senses = []
					for sense in senses:
						hypernyms.update(sense.hypernyms())
				resulthe.append(len(hypernyms))
		return resulthe
	
	def hyponymCount(self, data, args):
		resultho = []
		for line in data:
			for subst in line[3:len(line)]:
				words = subst.strip().split(':')[1].strip()
				hyponyms = set([])
				for word in words.split(' '):
					senses = None
					try:
						senses = wn.synsets(word)
					except UnicodeDecodeError:
						senses = []
					for sense in senses:
						hyponyms.update(sense.hyponyms())
				resultho.append(len(hyponyms))
		return resultho
	
	def minDepth(self, data, args):
		resultmi = []
		for line in data:
			for subst in line[3:len(line)]:
				words = subst.strip().split(':')[1].strip()
				mindepth = 9999999
				for word in words.split(' '):
					senses = None
					try:
						senses = wn.synsets(word)
					except UnicodeDecodeError:
						senses = []
					for sense in senses:
						auxmin = sense.min_depth()
						if auxmin<mindepth:
							mindepth = auxmin
				resultmi.append(mindepth)
		return resultmi
	
	def maxDepth(self, data, args):
		resultma = []
		for line in data:
			for subst in line[3:len(line)]:
				words = subst.strip().split(':')[1].strip()
				maxdepth = -1
				for word in words.split(' '):
					senses = None
					try:
						senses = wn.synsets(word)
					except UnicodeDecodeError:
						senses = []
					for sense in senses:
						auxmax = sense.max_depth()
						if auxmax>maxdepth:
							maxdepth = auxmax
				resultma.append(maxdepth)
		return resultma
		
	def readNgramFile(self, ngram_file):
		counts = shelve.open(ngram_file, protocol=pickle.HIGHEST_PROTOCOL)
		return counts
	
	def addWordVectorValues(self, model, size, orientation):
		"""
		Adds all the word vector values of a model to the estimator.
	
		@param model: Path to a binary word vector model.
		For instructions on how to create the model, please refer to the LEXenstein Manual.
		@param size: Number of feature values that represent a word in the model.
		@param orientation: Whether the feature is a simplicity of complexity measure.
		Possible values: Complexity, Simplicity.
		"""
		
		if orientation not in ['Complexity', 'Simplicity']:
			print('Orientation must be Complexity or Simplicity')
		else:
			if model not in self.resources.keys():
				m = gensim.models.word2vec.Word2Vec.load_word2vec_format(model, binary=True)
				self.resources[model] = m
			self.features.append((self.wordVectorValuesFeature, [model, size]))
			for i in range(0, size):
				self.identifiers.append(('Word Vector Value '+str(i)+' (Model: '+model+')', orientation))
	
	def addTargetPOSTagProbability(self, condprob_model, pos_model, stanford_tagger, java_path, orientation):
		"""
		Adds a target POS tag probability feature to the estimator.
		The value will be the conditional probability between a candidate substitution and the POS tag of a given target word.
	
		@param condprob_model: Path to a binary conditional probability model.
		For instructions on how to create the model, please refer to the LEXenstein Manual.
		@param pos_model: Path to a POS tagging model for the Stanford POS Tagger.
		The models can be downloaded from the following link: http://nlp.stanford.edu/software/tagger.shtml
		@param stanford_tagger: Path to the "stanford-postagger.jar" file.
		The tagger can be downloaded from the following link: http://nlp.stanford.edu/software/tagger.shtml
		@param java_path: Path to the system's "java" executable.
		Can be commonly found in "/usr/bin/java" in Unix/Linux systems, or in "C:/Program Files/Java/jdk_version/java.exe" in Windows systems.
		@param orientation: Whether the feature is a simplicity of complexity measure.
		Possible values: Complexity, Simplicity.
		"""
		
		if orientation not in ['Complexity', 'Simplicity']:
			print('Orientation must be Complexity or Simplicity')
		else:
			os.environ['JAVAHOME'] = java_path
			if pos_model not in self.resources.keys():
				tagger = StanfordPOSTagger(pos_model, stanford_tagger)
				self.resources[pos_model] = tagger
			if condprob_model not in self.resources.keys():
				m = pickle.load(open(condprob_model, 'rb'))
				self.resources[condprob_model] = m
			
			self.features.append((self.targetPOSTagProbability, [condprob_model, pos_model]))
			self.identifiers.append(('Target POS Tag Probability (Model:'+str(condprob_model)+')', orientation))
	
	def addWordVectorSimilarityFeature(self, model, orientation):
		"""
		Adds a word vector similarity feature to the estimator.
		The value will be the similarity between the word vector of a target complex word and the word vector of a candidate.
	
		@param model: Path to a binary word vector model.
		For instructions on how to create the model, please refer to the LEXenstein Manual.
		@param orientation: Whether the feature is a simplicity of complexity measure.
		Possible values: Complexity, Simplicity.
		"""
		
		if orientation not in ['Complexity', 'Simplicity']:
			print('Orientation must be Complexity or Simplicity')
		else:
			if model not in self.resources.keys():
				m = gensim.models.word2vec.Word2Vec.load_word2vec_format(model, binary=True)
				self.resources[model] = m
			self.features.append((self.wordVectorSimilarityFeature, [model]))
			self.identifiers.append(('Word Vector Similarity (Model: '+model+')', orientation))
			
	def addTaggedWordVectorSimilarityFeature(self, model, pos_model, stanford_tagger, java_path, pos_type, orientation):
		"""
		Adds a tagged word vector similarity feature to the estimator.
		The value will be the similarity between the word vector of a target complex word and the word vector of a candidate, while accompanied by their POS tags.
		Each entry in the word vector model must be in the following format: <word>|||<tag>
		To create a corpus for such model to be trained, one must tag each word in a corpus, and then concatenate words and tags using the aforementioned convention.
	
		@param model: Path to a binary word vector model.
		For instructions on how to create the model, please refer to the LEXenstein Manual.
		@param pos_model: Path to a POS tagging model for the Stanford POS Tagger.
		The models can be downloaded from the following link: http://nlp.stanford.edu/software/tagger.shtml
		@param stanford_tagger: Path to the "stanford-postagger.jar" file.
		The tagger can be downloaded from the following link: http://nlp.stanford.edu/software/tagger.shtml
		@param java_path: Path to the system's "java" executable.
		Can be commonly found in "/usr/bin/java" in Unix/Linux systems, or in "C:/Program Files/Java/jdk_version/java.exe" in Windows systems.
		@param pos_type: The type of POS tags to be used.
		Values supported: treebank, paetzold
		@param orientation: Whether the feature is a simplicity of complexity measure.
		Possible values: Complexity, Simplicity.
		"""
		
		if orientation not in ['Complexity', 'Simplicity']:
			print('Orientation must be Complexity or Simplicity')
		else:
			if model not in self.resources.keys():
				m = gensim.models.word2vec.Word2Vec.load_word2vec_format(model, binary=True)
				self.resources[model] = m
			if pos_model not in self.resources.keys():
				tagger = StanfordPOSTagger(pos_model, stanford_tagger)
				self.resources[pos_model] = tagger
			self.features.append((self.taggedWordVectorSimilarityFeature, [model, pos_model, pos_type]))
			self.identifiers.append(('Word Vector Similarity (Model: '+model+') (POS Model: '+pos_model+') (POS Type: '+pos_type+')', orientation))
	
	def addTranslationProbabilityFeature(self, translation_probabilities, orientation):
		"""
		Adds a translation probability feature to the estimator.
		The value will be the probability of a target complex word of being translated into a given candidate substitution.
	
		@param translation_probabilities: Path to a file containing the translation probabilities.
		The file must produced by the following command through fast_align:
		fast_align -i <parallel_data> -v -d -o <translation_probabilities_file>
		@param orientation: Whether the feature is a simplicity of complexity measure.
		Possible values: Complexity, Simplicity.
		"""
		path = translation_probabilities
		probabilities = {}
		f = open(path)
		for line in f:
			lined = line.strip().split('\t')
			word1 = lined[0]
			word2 = lined[1]
			prob = math.exp(float(lined[2]))
			if word1 in probabilities.keys():
				probabilities[word1][word2] = prob
			else:
				probabilities[word1] = {word2:prob}
		f.close()
		
		if orientation not in ['Complexity', 'Simplicity']:
			print('Orientation must be Complexity or Simplicity')
		else:
			if translation_probabilities not in self.resources.keys():
				self.resources[translation_probabilities] = probabilities
			self.features.append((self.translationProbabilityFeature, [translation_probabilities]))
			self.identifiers.append(('Translation Probability (File: '+translation_probabilities+')', orientation))
	
	def addLexiconFeature(self, lexicon, orientation):
		"""
		Adds a lexicon feature to the estimator.
		The value will be 1 if a given candidate is in the provided lexicon, and 0 otherwise.
	
		@param lexicon: Path to a file containing the words of the lexicon.
		The file must have one word per line.
		@param orientation: Whether the feature is a simplicity of complexity measure.
		Possible values: Complexity, Simplicity.
		"""
		
		if orientation not in ['Complexity', 'Simplicity']:
			print('Orientation must be Complexity or Simplicity')
		else:
			if lexicon not in self.resources.keys():
				words = set([w.strip() for w in open(lexicon)])
				self.resources[lexicon] = words
			self.features.append((self.lexiconFeature, [lexicon]))
			self.identifiers.append(('Lexicon Occurrence (Lexicon: '+lexicon+')', orientation))
	
	def addLengthFeature(self, orientation):
		"""
		Adds a word length feature to the estimator.
		The value will be the number of characters in each candidate.
	
		@param orientation: Whether the feature is a simplicity of complexity measure.
		Possible values: Complexity, Simplicity.
		"""
		
		if orientation not in ['Complexity', 'Simplicity']:
			print('Orientation must be Complexity or Simplicity')
		else:
			self.features.append((self.lengthFeature, []))
			self.identifiers.append(('Word Length', orientation))
	
	def addSyllableFeature(self, mat, orientation):
		"""
		Adds a syllable count feature to the estimator.
		The value will be the number of syllables of each candidate.
	
		@param mat: A configured MorphAdornerToolkit object.
		@param orientation: Whether the feature is a simplicity of complexity measure.
		Possible values: Complexity, Simplicity.
		"""
		
		if orientation not in ['Complexity', 'Simplicity']:
			print('Orientation must be Complexity or Simplicity')
		else:
			self.features.append((self.syllableFeature, [mat]))
			self.identifiers.append(('Syllable Count', orientation))
		
	def addCollocationalFeature(self, language_model, leftw, rightw, orientation):
		"""
		Adds a set of collocational features to the estimator.
		The values will be the language model probabilities of all collocational features selected.
		Each feature is the probability of an n-gram with 0<=l<=leftw tokens to the left and 0<=r<=rightw tokens to the right.
		This method creates (leftw+1)*(rightw+1) features.
	
		@param language_model: Path to the language model from which to extract probabilities.
		@param leftw: Maximum number of tokens to the left.
		@param rightw: Maximum number of tokens to the right.
		@param orientation: Whether the feature is a simplicity of complexity measure.
		Possible values: Complexity, Simplicity.
		"""
		
		if orientation not in ['Complexity', 'Simplicity']:
			print('Orientation must be Complexity or Simplicity')
		else:
			if language_model not in self.resources.keys():
				model = kenlm.LanguageModel(language_model)
				self.resources[language_model] = model
			self.features.append((self.collocationalFeature, [language_model, leftw, rightw]))
			for i in range(0, leftw+1):
				for j in range(0, rightw+1):
					self.identifiers.append(('Collocational Feature ['+str(i)+', '+str(j)+'] (LM: '+language_model+')', orientation))
					
	def addFrequencyCollocationalFeature(self, ngram_file, leftw, rightw, orientation):
		"""
		Adds a set of frequency collocational features to the estimator.
		The values will be the n-gram frequencies of all collocational features selected.
		Each feature is the frequency of an n-gram with 0<=l<=leftw tokens to the left and 0<=r<=rightw tokens to the right.
		This method creates (leftw+1)*(rightw+1) features.
	
		@param ngram_file: Path to a shelve file containing n-gram frequency counts.
		To produce this file, use the "addNgramCountsFileToShelve" function from the "util" module.
		@param leftw: Maximum number of tokens to the left.
		@param rightw: Maximum number of tokens to the right.
		@param orientation: Whether the feature is a simplicity of complexity measure.
		Possible values: Complexity, Simplicity.
		"""
		
		if orientation not in ['Complexity', 'Simplicity']:
			print('Orientation must be Complexity or Simplicity')
		else:
			if ngram_file not in self.resources.keys():
				counts = self.readNgramFile(ngram_file)
				self.resources[ngram_file] = counts
			self.features.append((self.frequencyCollocationalFeature, [ngram_file, leftw, rightw]))
			for i in range(0, leftw+1):
				for j in range(0, rightw+1):
					self.identifiers.append(('Frequency Collocational Feature ['+str(i)+', '+str(j)+'] (N-Grams File: '+ngram_file+')', orientation))
					
	def addTaggedFrequencyCollocationalFeature(self, ngram_file, leftw, rightw, pos_model, stanford_tagger, java_path, pos_type, orientation):
		"""
		Adds a set of frequency tagged n-gram frequency features to the estimator.
		The values will be the n-gram frequencies of all tagged collocational features selected.
		Each feature is the frequency of an n-gram with 0<=l<=leftw tagged tokens to the left and 0<=r<=rightw tagged tokens to the right.
		This method creates (leftw+1)*(rightw+1) features.
	
		@param ngram_file: Path to a shelve file containing n-gram frequency counts.
		This function requires for a special type of ngram_file.
		Each n-gram in the file must be composed of n-1 tags, and exactly 1 word.
		To produce this file, parse a corpus, extract n-grams in the aforementioned above, and use the "addNgramCountsFileToShelve" function from the "util" module.
		@param leftw: Maximum number of tokens to the left.
		@param rightw: Maximum number of tokens to the right.
		@param pos_model: Path to a POS tagging model for the Stanford POS Tagger.
		The models can be downloaded from the following link: http://nlp.stanford.edu/software/tagger.shtml
		@param stanford_tagger: Path to the "stanford-postagger.jar" file.
		The tagger can be downloaded from the following link: http://nlp.stanford.edu/software/tagger.shtml
		@param java_path: Path to the system's "java" executable.
		Can be commonly found in "/usr/bin/java" in Unix/Linux systems, or in "C:/Program Files/Java/jdk_version/java.exe" in Windows systems.
		@param pos_type: The type of POS tags to be used.
		Values supported: treebank, paetzold
		@param orientation: Whether the feature is a simplicity of complexity measure.
		Currently supported types: treebank, paetzold.
		Possible values: Complexity, Simplicity.
		"""
		
		if orientation not in ['Complexity', 'Simplicity']:
			print('Orientation must be Complexity or Simplicity')
		else:
			if ngram_file not in self.resources.keys():
				counts = self.readNgramFile(ngram_file)
				self.resources[ngram_file] = counts
			os.environ['JAVAHOME'] = java_path
			if pos_model not in self.resources.keys():
				tagger = StanfordPOSTagger(pos_model, stanford_tagger)
				self.resources[pos_model] = tagger
			self.features.append((self.taggedFrequencyCollocationalFeature, [ngram_file, leftw, rightw, pos_model, pos_type]))
			for i in range(0, leftw+1):
				for j in range(0, rightw+1):
					self.identifiers.append(('Tagged Frequency Collocational Feature ['+str(i)+', '+str(j)+'] (N-Grams File: '+ngram_file+') (POS type: '+pos_type+')', orientation))
	
	def addBinaryTaggedFrequencyCollocationalFeature(self, ngram_file, leftw, rightw, pos_model, stanford_tagger, java_path, pos_type, orientation):
		"""
		Adds a set of binary tagged frequency collocational features to the estimator.
		The values will be the binary n-gram values of all tagged collocational features selected.
		Each feature is the frequency of an n-gram with 0<=l<=leftw tagged tokens to the left and 0<=r<=rightw tagged tokens to the right.
		This method creates (leftw+1)*(rightw+1) features.
	
		@param ngram_file: Path to a shelve file containing n-gram frequency counts.
		This function requires for a special type of ngram_file.
		Each n-gram in the file must be composed of n-1 tags, and exactly 1 word.
		To produce this file, parse a corpus, extract n-grams in the aforementioned above, and use the "addNgramCountsFileToShelve" function from the "util" module.
		@param leftw: Maximum number of tokens to the left.
		@param rightw: Maximum number of tokens to the right.
		@param pos_model: Path to a POS tagging model for the Stanford POS Tagger.
		The models can be downloaded from the following link: http://nlp.stanford.edu/software/tagger.shtml
		@param stanford_tagger: Path to the "stanford-postagger.jar" file.
		The tagger can be downloaded from the following link: http://nlp.stanford.edu/software/tagger.shtml
		@param java_path: Path to the system's "java" executable.
		Can be commonly found in "/usr/bin/java" in Unix/Linux systems, or in "C:/Program Files/Java/jdk_version/java.exe" in Windows systems.
		@param pos_type: The type of POS tags to be used.
		Values supported: treebank, paetzold
		@param orientation: Whether the feature is a simplicity of complexity measure.
		Currently supported types: treebank, paetzold.
		Possible values: Complexity, Simplicity.
		"""
		
		if orientation not in ['Complexity', 'Simplicity']:
			print('Orientation must be Complexity or Simplicity')
		else:
			if ngram_file not in self.resources.keys():
				counts = self.readNgramFile(ngram_file)
				self.resources[ngram_file] = counts
			os.environ['JAVAHOME'] = java_path
			if pos_model not in self.resources.keys():
				tagger = StanfordPOSTagger(pos_model, stanford_tagger)
				self.resources[pos_model] = tagger
			self.features.append((self.binaryTaggedFrequencyCollocationalFeature, [ngram_file, leftw, rightw, pos_model, pos_type]))
			for i in range(0, leftw+1):
				for j in range(0, rightw+1):
					self.identifiers.append(('Binary Tagged Frequency Collocational Feature ['+str(i)+', '+str(j)+'] (N-Grams File: '+ngram_file+') (POS type: '+pos_type+')', orientation))
	
	def addPopCollocationalFeature(self, language_model, leftw, rightw, orientation):
		"""
		Adds a set of "pop" collocational features to the estimator.
		Each feature is the probability of an n-gram with 0<=l<=leftw tokens to the left and 0<=r<=rightw tokens to the right.
		The value of each feature will be the highest frequency between all "popping" n-gram combinations of one token to the left and right.
		This method creates (leftw+1)*(rightw+1) features.
	
		@param language_model: Path to the language model from which to extract probabilities.
		@param leftw: Maximum number of tokens to the left.
		@param rightw: Maximum number of tokens to the right.
		@param orientation: Whether the feature is a simplicity of complexity measure.
		Possible values: Complexity, Simplicity.
		"""
		
		if orientation not in ['Complexity', 'Simplicity']:
			print('Orientation must be Complexity or Simplicity')
		else:
			if language_model not in self.resources.keys():
				model = kenlm.LanguageModel(language_model)
				self.resources[language_model] = model
			self.features.append((self.popCollocationalFeature, [language_model, leftw, rightw]))
			for i in range(0, leftw+1):
				for j in range(0, rightw+1):
					self.identifiers.append(('Pop Collocational Feature ['+str(i)+', '+str(j)+'] (LM: '+language_model+')', orientation))
					
	def addNGramProbabilityFeature(self, language_model, leftw, rightw, orientation):
		"""
		Adds a n-gram probability feature to the estimator.
		The value will be the language model probability of the n-gram composed by leftw tokens to the left and rightw tokens to the right of a given word.
	
		@param language_model: Path to the language model from which to extract probabilities.
		@param leftw: Number of tokens to the left.
		@param rightw: Number of tokens to the right.
		@param orientation: Whether the feature is a simplicity of complexity measure.
		Possible values: Complexity, Simplicity.
		"""
		
		if orientation not in ['Complexity', 'Simplicity']:
			print('Orientation must be Complexity or Simplicity')
		else:
			if language_model not in self.resources.keys():
				model = kenlm.LanguageModel(language_model)
				self.resources[language_model] = model
			self.features.append((self.ngramProbabilityFeature, [language_model, leftw, rightw]))
			self.identifiers.append(('N-Gram Probability Feature ['+str(leftw)+', '+str(rightw)+'] (LM: '+language_model+')', orientation))
			
	def addNGramFrequencyFeature(self, ngram_file, leftw, rightw, orientation):
		"""
		Adds a n-gram frequency feature to the estimator.
		The value will be the the frequency of the n-gram composed by leftw tokens to the left and rightw tokens to the right of a given word.
	
		@param ngram_file: Path to a file with n-gram frequencies.
		@param leftw: Number of tokens to the left.
		@param rightw: Number of tokens to the right.
		@param orientation: Whether the feature is a simplicity of complexity measure.
		Possible values: Complexity, Simplicity.
		"""
		
		if orientation not in ['Complexity', 'Simplicity']:
			print('Orientation must be Complexity or Simplicity')
		else:
			if ngram_file not in self.resources.keys():
				counts = self.readNgramFile(ngram_file)
				self.resources[ngram_file] = counts
			self.features.append((self.ngramFrequencyFeature, [ngram_file, leftw, rightw]))
			self.identifiers.append(('N-Gram Frequency Feature ['+str(leftw)+', '+str(rightw)+'] (N-grams File: '+ngram_file+')', orientation))
			
	def addBinaryNGramFrequencyFeature(self, ngram_file, leftw, rightw, orientation):
		"""
		Adds a binary n-gram frequency feature to the estimator.
		The value will be 1 if the n-gram composed by leftw tokens to the left and rightw tokens to the right of a given word are in the n-grams file, and 0 otherwise.
	
		@param ngram_file: Path to a file with n-gram frequencies.
		@param leftw: Number of tokens to the left.
		@param rightw: Number of tokens to the right.
		@param orientation: Whether the feature is a simplicity of complexity measure.
		Possible values: Complexity, Simplicity.
		"""
		
		if orientation not in ['Complexity', 'Simplicity']:
			print('Orientation must be Complexity or Simplicity')
		else:
			if ngram_file not in self.resources.keys():
				counts = self.readNgramFile(ngram_file)
				self.resources[ngram_file] = counts
			self.features.append((self.binaryNgramFrequencyFeature, [ngram_file, leftw, rightw]))
			self.identifiers.append(('Binary N-Gram Probability Feature ['+str(leftw)+', '+str(rightw)+'] (N-grams File: '+ngram_file+')', orientation))
			
	def addPopNGramProbabilityFeature(self, language_model, leftw, rightw, orientation):
		"""
		Adds a pop n-gram probability feature to the estimator.
		The value is the highest probability of the n-gram with leftw tokens to the left and rightw tokens to the right, with a popping window of one token to the left and right.
	
		@param language_model: Path to the language model from which to extract probabilities.
		@param leftw: Number of tokens to the left.
		@param rightw: Number of tokens to the right.
		@param orientation: Whether the feature is a simplicity of complexity measure.
		Possible values: Complexity, Simplicity.
		"""
		
		if orientation not in ['Complexity', 'Simplicity']:
			print('Orientation must be Complexity or Simplicity')
		else:
			if language_model not in self.resources.keys():
				model = kenlm.LanguageModel(language_model)
				self.resources[language_model] = model
			self.features.append((self.popNgramProbabilityFeature, [language_model, leftw, rightw]))
			self.identifiers.append(('Pop N-Gram Frequency Feature ['+str(leftw)+', '+str(rightw)+'] (LM: '+language_model+')', orientation))
		
	def addSentenceProbabilityFeature(self, language_model, orientation):
		"""
		Adds a sentence probability feature to the estimator.
		The value will be the language model probability of each sentence in the VICTOR corpus with its target complex word replaced by a candidate.
	
		@param language_model: Path to the language model from which to extract probabilities.
		@param orientation: Whether the feature is a simplicity of complexity measure.
		Possible values: Complexity, Simplicity.
		"""
		if orientation not in ['Complexity', 'Simplicity']:
			print('Orientation must be Complexity or Simplicity')
		else:
			if language_model not in self.resources.keys():
				model = kenlm.LanguageModel(language_model)
				self.resources[language_model] = model
			self.features.append((self.sentenceProbabilityFeature, [language_model]))
			self.identifiers.append(('Sentence Probability (LM: '+language_model+')', orientation))
		
	def addSenseCountFeature(self, orientation):
		"""
		Adds a sense count feature to the estimator.
		Calculates the number of senses registered in WordNet of a candidate.
		
		@param orientation: Whether the feature is a simplicity of complexity measure.
		Possible values: Complexity, Simplicity.
		"""
		
		if orientation not in ['Complexity', 'Simplicity']:
			print('Orientation must be Complexity or Simplicity')
		else:
			self.features.append((self.senseCount ,[]))
			self.identifiers.append(('Sense Count', orientation))
		
	def addSynonymCountFeature(self, orientation):
		"""
		Adds a synonym count feature to the estimator.
		Calculates the number of synonyms registered in WordNet of a candidate.
		
		@param orientation: Whether the feature is a simplicity of complexity measure.
		Possible values: Complexity, Simplicity.
		"""
		
		if orientation not in ['Complexity', 'Simplicity']:
			print('Orientation must be Complexity or Simplicity')
		else:
			self.features.append((self.synonymCount ,[]))
			self.identifiers.append(('Synonym Count', orientation))
			
	def addIsSynonymFeature(self, orientation):
		"""
		Adds a synonymy relation feature to the estimator.
		If a candidate substitution is a synonym of the target word, then it returns 1, if not, it returns 0.
		
		@param orientation: Whether the feature is a simplicity of complexity measure.
		Possible values: Complexity, Simplicity.
		"""
		
		if orientation not in ['Complexity', 'Simplicity']:
			print('Orientation must be Complexity or Simplicity')
		else:
			self.features.append((self.isSynonym ,[]))
			self.identifiers.append(('Is Synonym', orientation))
		
	def addHypernymCountFeature(self, orientation):
		"""
		Adds a hypernym count feature to the estimator.
		Calculates the number of hypernyms registered in WordNet of a candidate.
		
		@param orientation: Whether the feature is a simplicity of complexity measure.
		Possible values: Complexity, Simplicity.
		"""
		
		if orientation not in ['Complexity', 'Simplicity']:
			print('Orientation must be Complexity or Simplicity')
		else:
			self.features.append((self.hypernymCount ,[]))
			self.identifiers.append(('Hypernym Count', orientation))
		
	def addHyponymCountFeature(self, orientation):
		"""
		Adds a hyponym count feature to the estimator.
		Calculates the number of hyponyms registered in WordNet of a candidate.
		
		@param orientation: Whether the feature is a simplicity of complexity measure.
		Possible values: Complexity, Simplicity.
		"""
		
		if orientation not in ['Complexity', 'Simplicity']:
			print('Orientation must be Complexity or Simplicity')
		else:
			self.features.append((self.hyponymCount ,[]))
			self.identifiers.append(('Hyponym Count', orientation))
		
	def addMinDepthFeature(self, orientation):
		"""
		Adds a minimum sense depth feature to the estimator.
		Calculates the minimum distance between two senses of a given candidate.
		
		@param orientation: Whether the feature is a simplicity of complexity measure.
		Possible values: Complexity, Simplicity.
		"""
		
		if orientation not in ['Complexity', 'Simplicity']:
			print('Orientation must be Complexity or Simplicity')
		else:
			self.features.append((self.minDepth ,[]))
			self.identifiers.append(('Minimal Sense Depth', orientation))
		
	def addMaxDepthFeature(self, orientation):
		"""
		Adds a maximum sense depth feature to the estimator.
		Calculates the maximum distance between two senses of a given candidate.
		
		@param orientation: Whether the feature is a simplicity of complexity measure.
		Possible values: Complexity, Simplicity.
		"""
		
		if orientation not in ['Complexity', 'Simplicity']:
			print('Orientation must be Complexity or Simplicity')
		else:
			self.features.append((self.maxDepth ,[]))
			self.identifiers.append(('Maximal Sense Depth', orientation))
