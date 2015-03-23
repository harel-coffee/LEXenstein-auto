
class GeneratorEvaluator:

	def evaluateGenerator(self, victor_corpus, substitutions):
		"""
		Performs an intrinsic evaluation of a Substitution Generation approach.
	
		@param victor_corpus: Path to a training corpus in VICTOR format.
		For more information about the file's format, refer to the LEXenstein Manual.
		@param substitutions: A dictionary that assigns target complex words to sets of candidate substitutions.
		Example: substitutions['perched'] = {'sat', 'roosted'}
		@return: Values for Potential, Precision and F-measure for the substitutions provided as input with respect to the gold-standard in the VICTOR corpus.
		For more information on how the metrics are calculated, please refer to the LEXenstein Manual.
		"""
		
		#Initialize variables:
		precisionc = 0
		precisiont = 0
		recallc = 0
		recallt = 0
		
		#Calculate measures:
		f = open(victor_corpus)
		for line in f:
			data = line.strip().split('\t')
			target = data[1].strip()
			items = data[3:len(data)]
			candidates = [item.strip().split(':')[1].strip() for item in items]
			if target in substitutions.keys():
				overlap = set(candidates).intersection(set(substitutions[target]))
				recallc += len(overlap)
				if len(overlap)>0:
					precisionc += 1
			precisiont += 1
			recallt += len(candidates)
		f.close()
		
		potential = float(precisionc)/float(precisiont)
		precision = float(recallc)/float(recallt)
		fmean = 0.0
		if potential==0.0 and noise==0.0:
			fmean = 0.0
		else:
			fmean = 2*(potential*noise)/(potential+noise)
			
		#Return measures:
		return potential, precision, fmean

class SelectorEvaluator:

	def evaluateSelector(self, victor_corpus, substitutions):
		"""
		Performs an intrinsic evaluation of a Substitution Selection approach.
	
		@param victor_corpus: Path to a training corpus in VICTOR format.
		For more information about the file's format, refer to the LEXenstein Manual.
		@param substitutions: A vector of size N, containing a set of selected substitutions for each instance in the VICTOR corpus.
		@return: Values for Potential, Precision and F-measure for the substitutions provided as input with respect to the gold-standard in the VICTOR corpus.
		For more information on how the metrics are calculated, please refer to the LEXenstein Manual.
		"""
	
		#Initialize variables:
		precisionc = 0
		precisiont = 0
		recallc = 0
		recallt = 0
		
		#Calculate measures:
		f = open(victor_corpus)
		index = -1
		for line in f:
			index += 1
		
			data = line.strip().split('\t')
			target = data[1].strip()
			items = data[3:len(data)]
			candidates = [item.strip().split(':')[1].strip() for item in items]
			
			selected = substitutions[index]
			if len(selected)>0:
				overlap = set(candidates).intersection(set(selected))
				recallc += len(overlap)
				if len(overlap)>0:
					precisionc += 1
			precisiont += 1
			recallt += len(candidates)
		f.close()

		#Return measures:
		potential = float(precisionc)/float(precisiont)
		precision = float(recallc)/float(recallt)
		fmean = 0.0
		if potential==0.0 and noise==0.0:
			fmean = 0.0
		else:
			fmean = 2*(potential*noise)/(potential+noise)
			
		#Return measures:
		return potential, precision, fmean

class RankerEvaluator:

	def evaluateRanker(self, victor_corpus, rankings):
		"""
		Performs an intrinsic evaluation of a Substitution Ranking approach.
	
		@param victor_corpus: Path to a training corpus in VICTOR format.
		For more information about the file's format, refer to the LEXenstein Manual.
		@param rankings: A vector of size N, containing a set of ranked substitutions for each instance in the VICTOR corpus.
		@return: Values for TRank and Recall for the substitutions provided as input with respect to the gold-standard in the VICTOR corpus.
		For more information on how the metrics are calculated, please refer to the LEXenstein Manual.
		"""
		
		#Initialize variables:
		total1 = 0
		total2 = 0
		total3 = 0
		corrects1 = 0
		corrects2 = 0
		corrects3 = 0
		recall1 = 0
		recall2 = 0
		recall3 = 0
		trecall1 = 0
		trecall2 = 0
		trecall3 = 0
	
		#Read data:
		index = -1
		f = open(victor_corpus)
		for data in f:
			index += 1
			line = data.strip().split('\t')
			gold_rankings = {}
			for subst in line[3:len(line)]:
				subst_data = subst.strip().split(':')
				word = subst_data[1].strip()
				ranking = int(subst_data[0].strip())
				gold_rankings[word] = ranking
			ranked_candidates = rankings[index]

			first = gold_rankings[ranked_candidates[0]]
	
			#Get recall sets:
			set1, set2, set3 = self.getRecallSets(line[3:len(line)])
			rankedset1 = set([])
			rankedset2 = set([])
			rankedset3 = set([])
	
			#Calculate TRank 1:
			if first==1:
				rankedset1 = set([ranked_candidates[0]])
				corrects1 += 1
			recall1 += len(rankedset1.intersection(set1))
			trecall1 += len(set1)
			total1 += 1
	
			#Calculate TRank 2:
			if len(gold_rankings.keys())>2:
				rankedset2 = rankedset1.union(set([ranked_candidates[1]]))
				recall2 += len(rankedset2.intersection(set2))
				trecall2 += len(set2)
				if first<=2:
					corrects2 += 1
				total2 += 1
	
			#Calculate TRank 3:
			if len(gold_rankings.keys())>3:
				rankedset3 = rankedset2.union(set([ranked_candidates[2]]))
				recall3 += len(rankedset3.intersection(set3))
				trecall3 += len(set3)
				if first<=3:
					corrects3 += 1
				total3 += 1
	
		#Return measures:
		return float(corrects1)/float(total1), float(corrects2)/float(total2), float(corrects3)/float(total3), float(recall1)/float(trecall1), float(recall2)/float(trecall2), float(recall3)/float(trecall3)
		
	def getRecallSets(self, substs):
		result1 = set([])
		result2 = set([])
		result3 = set([])
		for subst in substs:
			datasubst = subst.strip().split(':')
			word = datasubst[1].strip()
			index = datasubst[0].strip()
			if index=="1":
				result1.add(word)
				result2.add(word)
				result3.add(word)
			elif index=="2":
				result2.add(word)
				result3.add(word)
			elif index=="3":
				result3.add(word)
		return result1, result2, result3

class PipelineEvaluator:

	def evaluatePipeline(self, victor_corpus, rankings):
		"""
		Performs a round-trip evaluation of a Substitution Generation, Selection and Ranking approach combined.
	
		@param victor_corpus: Path to a training corpus in VICTOR format.
		For more information about the file's format, refer to the LEXenstein Manual.
		@param rankings: A list of ranked candidates for each instance in the VICTOR corpus, from simplest to most complex.
		One should produce candidates with a Substitution Generation approach, select them for a given VICTOR corpus with a Substitution Selection approach, then rank them with a Substitution Ranking approach.
		@return: Values for Precision, Accuracy and Changed Proportion for the substitutions provided as input with respect to the gold-standard in the VICTOR corpus.
		For more information on how the metrics are calculated, please refer to the LEXenstein Manual.
		"""
	
		#Initialize counting variables:
		total = 0
		totalc = 0
		precise = 0
		
		#Read victor corpus:
		f = open(victor_corpus)
		for i in range(0, len(rankings)):
			#Get gold candidates:
			data = f.readline().strip().split('\t')
			target = data[1].strip()
			data = data[3:len(data)]
			gold_subs = set([item.strip().split(':')[1].strip() for item in data])
			
			#Get highest ranked candidate:
			first = rankings[i][0]
			
			#Check if it is in gold candidates:
			total += 1
			if first!=target:
				totalc += 1
				if first in gold_subs:
					precise += 1
		
		#Return metrics:
		return float(precise)/float(totalc), float(precise)/float(total), float(totalc)/float(total)