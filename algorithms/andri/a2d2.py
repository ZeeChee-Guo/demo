import numpy as np
import matplotlib.pyplot as plt
from scipy.cluster.hierarchy import distance
# from util.util_overlap import *
# from util.adjacent_clustering import adaptive_ahc
import stumpy
import math

from algorithms.andri.util_a2d2 import *
from algorithms.andri.ahc import membership, adaptive_ahc
from algorithms.andri.plot_aadd import *
from tqdm.notebook import tqdm
# from sklearn.cluster import DBSCAN
import logging

colors = ['tab:blue', 'tab:orange', 'tab:green', 'tab:purple', 'tab:brown', 'tab:olive', 'tab:pink', 'tab:cyan', 'tab:gray', 
          'blue', 'orange', 'green', 'purple','brown', 'gold', 'violet', 'cyan', 'pink', 'deepskyblue', 'lawngreen',
          'royalblue', 'darkgrey', 'darkorange', 'darkgreen','darkviolet','salmon','olivedrab','lightcoral','darkcyan','yellowgreen']

class NormalModel:
    def __init__(self, subseq, tau, nu, c_m, c_std, active=True):
        self.subseq = subseq
        self.tau = tau
        self.nu = nu
        self.m = c_m
        self.std = c_std
        self.active = active

    def set_active(self, status):
        self.active = status

class windowL:
    def __init__(self, W, slidingWindow):
        self.W = W
        self.slidingWindow = slidingWindow
        self.NM = []
        self.mem = []
        self.seq = []
        self.dist = []
        self.avg_score = []
        self.prepare_add = False
        # self.cl = []

    def update_NM(self, NormalModel):
        self.NM.append(NormalModel)
        self.mem.append([])
        self.dist.append([])
        self.avg_score.append([])
        if len(self.seq) > 0:
            for se in self.seq:
                m_t, d_t = membership(NormalModel.subseq, se, NormalModel.tau, eta=1)
                self.mem[-1] = np.append(self.mem[-1], m_t)
                self.dist[-1] = np.append(self.dist[-1], d_t)
                self.avg_score[-1] = np.append(self.avg_score[-1], np.mean(self.dist[-1]))

    def enqueue(self, seq, idx):
        self.seq.append(seq)
        num_active = len([nm for nm in self.NM if nm.active == True])
        return_status = []

        ## computing membership function for all normal models and change activeness
        nm_turn_act, nm_turn_inact = [], []
        for i, nm in enumerate(self.NM):

            m_t, d_t = membership(nm.subseq, seq, nm.tau, eta=1)
            self.mem[i] = np.append(self.mem[i], m_t)
            self.dist[i] = np.append(self.dist[i], d_t)
            self.avg_score[i] = np.append(self.avg_score[i], np.mean(self.dist[i]))
            
            # if len(self.seq) <= self.W and self.prepare_add == False : continue    ## Fill init. windows

            ## Queuing W
            if len(self.seq) > self.W:
                self.mem[i] = np.delete(self.mem[i], 0)
                self.dist[i] = np.delete(self.dist[i], 0)
                self.avg_score[i] = np.delete(self.avg_score[i], 0)

                ## When checking stats, exclude the minimum membership in W
                curr_mem = copy.deepcopy(self.mem[i])
                if self.prepare_add: curr_mem = curr_mem[-(self.W//2):]
                curr_mem = np.delete(curr_mem, np.argmin(curr_mem))

                ## Active --> Inactive based on membership
                if nm.active == True and np.mean(curr_mem) < nm.nu:
                    print(f'[<-- Inactive]: NM {i} = {np.mean(curr_mem)}/{nm.nu}, at {idx}')
                    nm.set_active(False)
                    num_active -=1
                    # if num_active <=0:
                        # nm_f_idx =self.force_active()
                        # num_active = 1
                        # nm_turn_act.append(nm_f_idx)
                    return_status.append('inactive')
                    nm_turn_inact.append(i)

                ## Inactive --> Active based on membership
                elif nm.active == False and np.mean(curr_mem) >= nm.nu:
                    print(f'[--> Active]: NM {i} = {np.mean(curr_mem)}/{nm.nu}, at {idx}')
                    nm.set_active(True)
                    num_active +=1
                    return_status.append('active')
                    nm_turn_act.append(i)

        if len(self.seq) > self.W: 
            if self.prepare_add:
                return_status.append('add_NM')
            else:
                ## similar but small std cases
                nm_idx = np.argmax([np.mean(self.mem[i]) for i in range(len(self.NM))])
                nm = self.NM[nm_idx]
                if len(self.seq) > self.W and nm.active ==True and np.mean(self.mem[nm_idx]) > nm.nu:
                    if nm.tau < np.mean(self.dist[nm_idx])+3*np.std(self.dist[nm_idx]) and nm.std> np.std(self.dist[nm_idx]):
                        print(f'[{idx}], NM {i}, tau: {nm.tau:.2f} (M: {nm.m}, STD: {nm.std}) vs. {np.mean(self.dist[nm_idx])+3*np.mean(self.dist[nm_idx])}, (M: {np.mean(self.dist[nm_idx])}, STD: {np.mean(self.dist[nm_idx])})')
                        return_status.append('inactive')
                    # print(f'==> at {idx}: NM {i}, tau: {nm.tau:.2f}, but {np.mean(tmp_dist[:int(len(tmp_dist)*tmp_mem)])+3*np.std(tmp_dist[:int(len(tmp_dist)*tmp_mem)]):.2f}, (M: {np.mean(tmp_dist[:int(len(tmp_dist)*tmp_mem)]):.2f}, STD: {np.std(tmp_dist[:int(len(tmp_dist)*tmp_mem)]):.2f})')
                    # print(f'-- nu: {nm.nu:.2f}, avg_mem: {np.mean(self.mem[i]):.2f}, {nm.active}')
            
            del self.seq[0]

        if num_active <=0:
            nm_f_idx =self.force_active()
            num_active += 1
            return_status.append('active')
            nm_turn_act.append(nm_f_idx)

        return return_status, nm_turn_act, nm_turn_inact
        
    def terminate_add(self, org_W):
        if self.prepare_add: self.prepare_add = False
        if self.W > org_W:
            for j in range(self.W - org_W):
                for i, nm in enumerate(self.NM):
                    self.mem[i] = np.delete(self.mem[i], 0)
                    self.dist[i] = np.delete(self.dist[i], 0)
                    self.avg_score[i] = np.delete(self.avg_score[i], 0)
                del self.seq[0]
                
        self.W = org_W


    def force_active(self):
        # nm_mems = np.mean(self.mem[int(self.W/2):], axis=1)
        nm_mems = [np.mean(mem) for mem in self.mem]
        # print('CHK1: ', nm_mems)
        self.NM[int(np.argmax(nm_mems))].set_active(True)
        # print('FORCE:', int(np.argmax(nm_mems)), len(self.mem), [len(self.mem[i]) for i in range(len(self.NM))])
        # for i, nm in enumerate(self.NM):
            # if nm.active: print(f'[MEM] NM {i} = {nm_mems[i]}')
        return int(np.argmax(nm_mems))


class A2D2():

    def __init__(self,pattern_length, normalize='zero-mean', linkage_method='ward', th_reverse=5, kadj=1, nm_len=2, overlap=0.5, max_W = 15, eta=1, REFINE=True, REVISE_SCORE=True, device_id=0):
        self.pattern_length = pattern_length
        self.normalize=normalize     
        self.overlap = overlap
        self.linkage_method=linkage_method
        self.th_reverse=th_reverse
        self.kadj = kadj
        self.nm_len = nm_len
        self.seq_idx = 0
        self.eta = eta
        self.Z = []
        self.REFINE=REFINE
        self.REVISE_SCORE = REVISE_SCORE
        # self.div_seq = div_seq

        self.scores = np.array([])
        self.cl_s = np.array([])
        self.est_label = np.array([])
        self.max_W = max_W
        self.W = max_W

        self.listcluster = []
        self.cl_list = []
        self.mem_nm = []
        self.dist_nm = []
        self.device_id = device_id
    

    def __training(self, training_len, stump, stepwise, cut, min_size=0.025):
        """
        Training using Adjacent Hierarchical Clustering
        """
        x_train =  self.ts[:training_len]
        if self.y is not None: y_train = self.y[:training_len]
        
        ## Divide training set w/ subseq. length
        seqs_n = []
        if self.y is not None: n_subseq, n_label = divide_subseq(x_train, self.pattern_length, self.nm_len, overlap=self.overlap, label=y_train)
        else: n_subseq = divide_subseq(x_train, self.pattern_length, self.nm_len, overlap=self.overlap)
        # print(f'CHECK: {training_len} = {len(x_train)}, and {len(n_subseq)}, {len(n_subseq[0])}')
        ## normalize subseqences
        for seq in n_subseq: seqs_n.append(norm_seq(seq, self.normalize))
        seqs_n = np.array(seqs_n)
        
        ## Adjacent Hierarchical Clustering TODO: zero-mean vs. SBD
        listcluster, Z, m_subseq, m_tau, m_nu, _, __cached__, d_ci, d_c_std, Ws, _ = adaptive_ahc(seqs_n, linkage_method=self.linkage_method, th_reverse=self.th_reverse, kadj=self.kadj, eta=self.eta, max_W = self.max_W, cut=cut, min_size =min_size, REFINE=self.REFINE)

        if Ws is None: return None
        self.Z = Z
        # dendo = dendrogram(Z)
        
        self.W = int(np.min([self.max_W, 2*np.max(Ws)]))
        for i in range(len(m_tau)):
            print(f'NM: {i}, Tau: {m_tau[i]}, Nu: {m_nu[i]}, M: {d_ci[i]}, STD: {d_c_std[i]}')

        ## Normal Models
        self.NMs = []
        for m_s, m_t, m_n, m_m, m_std in zip(m_subseq, m_tau, m_nu, d_ci, d_c_std): self.NMs.append(NormalModel(m_s, m_t, m_n, m_m, m_std))
        for i in range(len(self.NMs)): 
            self.mem_nm.append([])
            self.dist_nm.append([])

        # print(f'[Num. of NM] ={len(self.NMs)}')
        # print(f'Set of listcluster: {set(list(listcluster))}')
        self.listcluster = listcluster
        cl_list = np.array([])
        for lc in listcluster: cl_list = np.append(cl_list, np.ones(int(self.pattern_length*self.nm_len*(1-self.overlap)))*lc)

        if len(cl_list) < len(x_train): cl_list = np.append(cl_list, np.ones(len(x_train)-len(cl_list))*(-1))
        self.cl_s = cl_list
        
        if stump:
            ## Compute anomaly score
            if self.normalize == 'z-norm': 
                normalize = True
            else:
                normalize = False
            self.scores, self.joins = offline_score(x_train, self.pattern_length, self.NMs, self.cl_s, normalize)
        else:
            self.cl_s = []
            before_status = False
            for i in range(0, len(x_train), self.pattern_length):
                x_test = x_train[i:i+self.pattern_length]
                x_test_n = norm_seq(x_test, self.normalize)
                for j, nm in enumerate(self.NMs): 
                    m_j, d_j = membership(nm.subseq, x_test_n, nm.tau, eta=1)
                    self.mem_nm[j] = np.append(self.mem_nm[j], m_j)
                    self.dist_nm[j] = np.append(self.dist_nm[j], d_j)

                score_cl, i_cl = [], []
                ## For cluster members
                if cl_list[i] != -1:
                    # print('[CL LIST]', cl_list[i], len(self.NMs))
                    nm_idx = int(cl_list[i])
                    score = np.linalg.norm(compute_diff_dist(self.NMs[nm_idx].subseq, x_test_n))
                    self.cl_s = np.append(self.cl_s, np.ones(self.pattern_length) * nm_idx)                

                else:
                    for j, nm in enumerate(self.NMs):
                        score_cl.append(np.linalg.norm(compute_diff_dist(nm.subseq, x_test_n)))

                    score = np.min(score_cl)
                    self.cl_s = np.append(self.cl_s, np.ones(self.pattern_length) * np.argmin(score_cl))
                    nm_idx = int(np.argmin(score_cl))
                # print('[Train-CL]', nm_idx, cl_list[i])   

                selected_nm = self.NMs[nm_idx]
                # if i < self.pattern_length: selected_nm = self.NMs[nm_idx]
                # elif self.cl_s[-1] == self.cl_s[-self.pattern_length-1]:
                    # selected_nm = self.NMs[nm_idx]
                # else:
                    # selected_nm = movingWin.NM[int(self.cl_s[-self.pattern_length-1])]
                selected_th = selected_nm.tau

                if stepwise:
                    if i >= self.pattern_length: x_tests = x_train[i-self.pattern_length:i+self.pattern_length]
                    else: x_tests = x_train[i:i+self.pattern_length*2]
                    rev_score = backward_anomaly2(x_tests, self.pattern_length, self.NMs[nm_idx].subseq, self.normalize, self.device_id)
                    if i >= self.pattern_length: self.scores = np.append(self.scores, rev_score[:self.pattern_length])
                    else: self.scores = np.append(self.scores, rev_score[:self.pattern_length//2])
                    # self.scores = np.append(self.scores, rev_score[:self.pattern_length])
                else:
                    ## Find sub-subseq. of anomalies
                    if score > selected_th:
                        tmp_score = backward_anomaly(x_train[i-self.pattern_length:i+self.pattern_length], self.pattern_length, self.NMs[nm_idx].subseq, self.normalize)
                        tmp_score = tmp_score/self.NMs[nm_idx].tau
                        # self.scores[-int(self.pattern_length/2):] = tmp_score[:int(self.pattern_length/2)]
                        # self.scores = np.append(self.scores, np.pad(tmp_score[int(self.pattern_length/2):], (0, int(self.pattern_length/2)), constant_values=tmp_score[-1]))
                        self.scores = np.append(self.scores, tmp_score)
                        before_status = True
                    else:
                        if before_status:
                            tmp_score = backward_anomaly(x_train[i-self.pattern_length:i+self.pattern_length], self.pattern_length, self.NMs[nm_idx].subseq, self.normalize)
                            tmp_score = tmp_score/self.NMs[nm_idx].tau
                            # self.scores[-int(self.pattern_length/2):] = tmp_score[:int(self.pattern_length/2)]
                            # self.scores = np.append(self.scores, np.pad(tmp_score[int(self.pattern_length/2):], (0, int(self.pattern_length/2)), constant_values=tmp_score[-1]))
                            self.scores = np.append(self.scores, tmp_score)
                        else:
                            self.scores = np.append(self.scores, np.ones(self.pattern_length)*score/self.NMs[nm_idx].tau)
                        before_status = False

                # if i%100==0:
                    # print(f'---------------- {i}/{len(self.ts)} ')


    def fit(self, X, y=None, online=True, training=True, delta=0, training_len=None, stump=False, stepwise=False, align=True, cut=None, min_size=0.025):
        ## if overlapping is not 1, revise for loop 
        self.ts = X
        self.y = y

        if online:
            if training_len < len(X)*0.1:
                print('[ERR]: Need to specify training length (>= 10% of data)')
                return 0
            
            self.__training(training_len, stump, stepwise, cut, min_size)
            print('Train:', training_len, 'vs', len(self.scores), 'start:', training_len)
            if len(self.scores) ==0:
                return None

            movingWin = windowL(self.W, self.pattern_length)
            ## Normal models are already saved.
            for nm in self.NMs: movingWin.update_NM(nm)

            # mem_nm = []
            # for i in range(len(self.NMs)): mem_nm.append([])

            print(f'START: {len(self.mem_nm)}, {len(self.mem_nm[0])}')

            ## Compute score for each subsequence 
            
            # for self.seq_idx in tqdm(range(training_len,len(X)-self.pattern_length, self.pattern_length)):
            self.seq_idx = training_len
            before_status = False

            while (self.seq_idx < len(X)):
                test_seq = self.ts[self.seq_idx:self.seq_idx+self.pattern_length]
                test_seq_n = norm_seq(test_seq, self.normalize)
                if len(test_seq) < self.pattern_length:
                    if stepwise:
                        x_tests = self.ts[self.seq_idx-self.pattern_length:]
                        if type(selected_nm) == list: selected_nm = selected_nm[0]
                        rev_score = backward_anomaly2(x_tests, self.pattern_length, selected_nm.subseq, self.normalize, self.device_id)
                        self.scores = np.append(self.scores, rev_score[:self.pattern_length])
                    print(f'Online scores len: {len(self.scores)}')
                    print('Done')
                    break

                rsts, nm_acts, nm_inacts = movingWin.enqueue(test_seq_n, self.seq_idx)

                ## Revise status
                # for rst, nm_act, nm_inact in zip(rsts, nm_acts, nm_inacts):
                ## (1) when at least one-inactive ==> prepare for adding new NM
                ## (2) when at least one-active: revise score
                ## (3) add_NM: initiate adding a new NM (? even if active exists?)

                if 'active' in rsts:
                    # chk_nu = [movingWin.NM[m].nu for m in nm_acts]
                    # idx_act = nm_acts[int(np.argmax(chk_nu))]
                    if self.REVISE_SCORE: self.revise_scores(movingWin, delta, nm_acts, stepwise, 'active')

                elif 'inactive' in rsts:
                    if movingWin.W == self.W:
                        movingWin.W = self.W*2
                        movingWin.prepare_add = True

                if 'add_NM' in rsts:
                    # print(f'W: {movingWin.W} & {movingWin.prepare_add}')
                    # new_NM, d_nm, new_len = self.add_new_NM(movingWin.seq, self.nm_len, self.overlap, movingWin.NM, self.seq_idx)
                    new_NM, d_nm, new_len = self.add_new_NM(self.ts[self.seq_idx-movingWin.W*self.pattern_length:self.seq_idx+self.pattern_length], self.nm_len, self.overlap, movingWin.NM, self.seq_idx)
                    if new_NM is not None:
                        if new_NM.tau > max([nm.tau for nm in self.NMs]): new_NM.tau = max([nm.tau for nm in self.NMs])
                        if new_NM.nu > max([nm.nu for nm in self.NMs]): new_NM.nu = max([nm.nu for nm in self.NMs])
                        self.NMs.append(new_NM)
                        movingWin.update_NM(new_NM)
                        # movingWin.mem[-1] = np.append(movingWin.mem[-1], membership(new_NM.subseq, test_seq_n, new_NM.tau, eta=self.eta))
                        self.mem_nm.append([])
                        self.dist_nm.append([])
                        # self.pattern_length = new_len
                        print(f'[==> Add NM]: NM# {len(self.NMs)-1}, TAU: {new_NM.tau}, Nu: {new_NM.nu}, LEN: {new_len}')

                        if self.REVISE_SCORE: self.revise_scores(movingWin, delta, len(self.NMs)-1, stepwise, 'new')

                    movingWin.terminate_add(self.W) ## (4) clear W (reset)
                
                for j in range(len(movingWin.NM)):
                    # print(f'++ {j} -->{len(movingWin.mem[j])}')
                    self.mem_nm[j] = np.append(self.mem_nm[j], movingWin.mem[j][-1])
                    self.dist_nm[j] = np.append(self.dist_nm[j], movingWin.dist[j][-1])

                ## Anomaly score with active normal patterns
                score_cl, i_cl, score_tau = [],[],[]
                for j, nm in enumerate(movingWin.NM):
                    if nm.active:
                        score_cl.append(movingWin.dist[j][-1])
                        # score_tau.append(score_cl[-1]/nm.tau)
                        i_cl.append(j)

                ## save current cluster, score
                score, nm_idx = np.min(score_cl), i_cl[np.argmin(score_cl)]
                # nm_idx = i_cl[np.argmin(score_tau)]
                # score = score_cl[np.argmin(score_tau)]
                self.cl_s = np.append(self.cl_s, nm_idx*np.ones(self.pattern_length))

                # self.update_score(movingWin, nm_idx, score, stepwise)
                if stepwise:
                    if self.seq_idx >= self.pattern_length:
                        x_tests = self.ts[self.seq_idx-self.pattern_length:self.seq_idx+self.pattern_length]
                    else: continue

                    ## Find sub-subseq. of anomalies
                    # selected_nm = movingWin.NM[nm_idx] if self.cl_s[-1] == self.cl_s[-self.pattern_length-1] else movingWin.NM[int(self.cl_s[-self.pattern_length-1])]
                    if self.cl_s[-1] == self.cl_s[-self.pattern_length-1]:
                        selected_nm = movingWin.NM[nm_idx]
                        rev_score = backward_anomaly2(x_tests, self.pattern_length, selected_nm.subseq, self.normalize, device_id=self.device_id)
                    else:
                        selected_nm = movingWin.NM[nm_idx]
                        rev_score = backward_anomaly2(x_tests, self.pattern_length, selected_nm.subseq, self.normalize, device_id=self.device_id)
                        # selected_nm = []
                        # selected_nm.append(movingWin.NM[int(self.cl_s[-self.pattern_length-1])])
                        # selected_nm.append(movingWin.NM[nm_idx])

                        ## Check mid-subseq
                        # score_cl_mid, i_cl_mid = [], []
                        # seq_mid = norm_seq(self.ts[self.seq_idx-(self.pattern_length//2):self.seq_idx+(self.pattern_length//2)], self.normalize)
                        # for nm_id, nm in enumerate(movingWin.NM):
                            # if nm.active: 
                                # score_cl_mid.append(np.linalg.norm(compute_diff_dist(nm.subseq, seq_mid)))
                                # i_cl_mid.append(nm_id)
                        ## print('SC:', score_cl_mid, i_cl_mid)
                        # nm_mid = i_cl_mid[np.argmin(score_cl_mid)]
                        # selected_nm.append(movingWin.NM[nm_mid])
                        # rev_score = backward_anomaly_changing_point(x_tests, self.pattern_length, selected_nm, self.normalize)
                    
                    self.scores = np.append(self.scores, rev_score[:self.pattern_length])
                else:
                    selected_th = selected_nm.tau
                    if score > selected_th:
                        # print(f'AT {self.seq_idx}, Score: {score}, NM: {nm_idx}, TAU: {selected_th}')
                        tmp_score = backward_anomaly(self.ts[self.seq_idx-self.pattern_length:self.seq_idx+self.pattern_length], self.pattern_length, selected_nm.subseq, self.normalize)
                        tmp_score = tmp_score/selected_th
                        self.scores = np.append(self.scores, tmp_score)
                        before_status = True
                    else:
                        if before_status:
                            tmp_score = backward_anomaly(self.ts[self.seq_idx-self.pattern_length:self.seq_idx+self.pattern_length], self.pattern_length, selected_nm.subseq, self.normalize)
                            tmp_score = tmp_score/selected_th
                            self.scores = np.append(self.scores, tmp_score)
                        else:
                            self.scores = np.append(self.scores, np.ones(self.pattern_length)*score/movingWin.NM[nm_idx].tau)
                        before_status=False
 
                self.seq_idx += self.pattern_length

                # if self.seq_idx%10000 ==0:
                    # print(f'{self.seq_idx}/{len(self.ts)}')

        ## Offline method
        else:
            self.__training(len(X), stump, stepwise, cut, min_size)
            print(f'Offline scores len: {len(self.scores)}')
            if len(self.scores) == 0:
                return None

        self.scores = np.append(self.scores, self.scores[-1]*np.ones(len(X)-len(self.scores)))
        if align:
            self.scores = align_score(self.NMs, self.scores, self.cl_s[:len(self.scores)], self.pattern_length)
        else:
            self.scores = running_mean(self.scores, self.pattern_length)
            self.scores = np.array([self.scores[0]]*((self.pattern_length-1)//2) + list(self.scores) + [self.scores[-1]]*((self.pattern_length-1)//2))
    
    ## Update scores and cl_s from curr_idx
    def update_score(self, movingWin, curr_idx, nm_idx, score, stepwise, before_status):
        self.cl_s[curr_idx:curr_idx+self.pattern_length] = np.ones(self.pattern_length)*nm_idx
        x_tests = self.ts[curr_idx-self.pattern_length:curr_idx+self.pattern_length]
        if stepwise:
            
            # selected_nm = movingWin.NM[nm_idx] if self.cl_s[-1] == self.cl_s[-self.pattern_length-1] else movingWin.NM[int(self.cl_s[-self.pattern_length-1])]
            if self.cl_s[curr_idx+1] == self.cl_s[curr_idx-self.pattern_length+1]:
                selected_nm = movingWin.NM[nm_idx]
                rev_score = backward_anomaly2(x_tests, self.pattern_length, selected_nm.subseq, self.normalize, device_id=self.device_id)
            else:
                selected_nm = []
                selected_nm.append(movingWin.NM[int(self.cl_s[curr_idx-self.pattern_length+1])])
                selected_nm.append(movingWin.NM[nm_idx])

                ## Check mid-subseq
                # score_cl_mid, i_cl_mid = [], []
                # seq_mid = norm_seq(self.ts[curr_idx-(self.pattern_length//2):curr_idx+(self.pattern_length//2)], self.normalize)
                # for nm_id, nm in enumerate(movingWin.NM):
                #     if nm.active: 
                #         score_cl_mid.append(np.linalg.norm(compute_diff_dist(nm.subseq, seq_mid)))
                #         i_cl_mid.append(nm_id)
                # # print('SC:', score_cl_mid, i_cl_mid)
                # nm_mid = i_cl_mid[np.argmin(score_cl_mid)]
                # selected_nm.append(movingWin.NM[nm_mid])
                rev_score = backward_anomaly_changing_point(x_tests, self.pattern_length, selected_nm, self.normalize, device_id=self.device_id)

            
        else:
            selected_nm = movingWin.NM[nm_idx]
            selected_th = selected_nm.tau
            if score > selected_th:
                # print(f'AT {self.seq_idx}, Score: {score}, NM: {nm_idx}, TAU: {selected_th}')
                tmp_score = backward_anomaly(x_tests, self.pattern_length, selected_nm.subseq, self.normalize)
                tmp_score = tmp_score/selected_th
                self.scores = np.append(self.scores, tmp_score)
                before_status = True
            else:
                if before_status:
                    tmp_score = backward_anomaly(x_tests, self.pattern_length, selected_nm.subseq, self.normalize)
                    rev_score = tmp_score/selected_th
                    # self.scores = np.append(self.scores, tmp_score)
                else:
                    # self.scores = np.append(self.scores, np.ones(self.pattern_length)*score/movingWin.NM[nm_idx].tau)
                    rev_score = np.ones(self.pattern_length)*score/movingWin.NM[nm_idx].tau
                before_status=False
                
        return rev_score, before_status


    ## After adding a new Normal Model, revise scores, cl_s, and memberships and distance for each NMs
    def revise_scores(self, movingWin, delta, nm_ids, stepwise, added='new', before_status=False):
        rev_cl_s,rev_scores = np.array([]), np.array([])
        before_status = False
        # start_idx = self.seq_idx - movingWin.W*self.pattern_length
        if delta > movingWin.W*self.pattern_length: delta = movingWin.W*self.pattern_length
        start_idx = self.seq_idx - (delta-delta%self.pattern_length)
        # print(f'*** After adding a new NM, WIN: {delta}, at {self.seq_idx} ==> {start_idx}')
        # print('BEFORE: ', len(self.scores))
        
        # for idx, seq in enumerate(movingWin.seq):
        while (start_idx < self.seq_idx):
            # test_seq = self.ts[start_idx:start_idx+self.pattern_length]
            curr_cl = int(self.cl_s[start_idx+1])
            win_idx = int((self.seq_idx - start_idx)/self.pattern_length) -1
            # print('WIN_IDX: ', win_idx, curr_cl, movingWin.W, len(movingWin.dist[curr_cl]), len(movingWin.seq), added)
            min_dist, min_j = movingWin.dist[curr_cl][-win_idx], curr_cl

            ## When active...
            if added == 'active':
                ## Compare movingWin.dist & movingWin.mem
                for j in nm_ids:
                    if min_dist > movingWin.dist[j][-win_idx]:
                        min_dist, min_j = movingWin.dist[j][-win_idx], j
                if min_j == curr_cl: 
                    start_idx += self.pattern_length
                    continue
                else:
                    ## update cl_s and scores
                    # self.cl_s[start_idx:start_idx+self.pattern_length] = np.ones(self.pattern_length)*j
                    rev_score, before_status = self.update_score(movingWin, start_idx, min_j, min_dist, stepwise, before_status)
                    self.scores[start_idx-self.pattern_length//2-1:start_idx-self.pattern_length//2-1 + self.pattern_length] = rev_score[:self.pattern_length]

            elif added == 'new':
                new_dist = np.linalg.norm(compute_diff_dist(movingWin.NM[nm_ids].subseq, self.ts[start_idx:start_idx+self.pattern_length]))
                if min_dist > new_dist:
                    min_dist, min_j = new_dist, nm_ids
                if min_j == curr_cl: 
                    start_idx += self.pattern_length
                    continue
                else:
                    rev_score, before_status = self.update_score(movingWin, start_idx, min_j, min_dist, stepwise, before_status)
                    self.scores[start_idx-self.pattern_length//2-1:start_idx-self.pattern_length//2-1 + self.pattern_length] = rev_score[:self.pattern_length]

                m_t, d_t = membership(movingWin.NM[nm_ids].subseq, self.ts[start_idx:start_idx+self.pattern_length], movingWin.NM[nm_ids].tau, eta=1)
                self.mem_nm[-1] = np.append(self.mem_nm[nm_ids], m_t) 
                self.dist_nm[-1] = np.append(self.dist_nm[nm_ids], d_t)
            else:
                return

            start_idx += self.pattern_length

#             score_cl, i_cl, score_tau = [],[],[]
#             for j, nm in enumerate(movingWin.NM):
#                 if nm.active:
#                     score_cl.append(np.linalg.norm(compute_diff_dist(nm.subseq, seq)))
#                     score_tau.append(score_cl[-1]/nm.tau)
#                     i_cl.append(j)
#             self.cl_s[start_idx + idx*len(seq):start_idx + (idx+1)*len(seq)] = nm_idx*np.ones(len(seq))
#             # print(f'{idx}  {movingWin.W}: {start_idx+idx*len(seq)}:{start_idx + (idx+1)*len(seq)} ==> {len(seq)}')
# 
#             ## Find sub-subseq. of anomalies
#             if self.cl_s[start_idx + (idx)*len(seq)-1] == self.cl_s[start_idx + (idx+1)*len(seq)-1]:
#                 selected_nm = movingWin.NM[nm_idx]
#             else:
#                 selected_nm = movingWin.NM[int(self.cl_s[start_idx + (idx+1)*len(seq)-1])]
#             # selected_nm = movingWin.NM[nm_idx]
#             selected_th = selected_nm.tau
# 
#             if stepwise:
#                 x_tests = self.ts[start_idx + (idx-1)*len(seq):start_idx + (idx+1)*len(seq)]
#                 rev_score = backward_anomaly2(x_tests, self.pattern_length, selected_nm.subseq, self.normalize)
#                 # print('==== ', len(x_tests), len(rev_score), len(self.scores[start_idx + idx*len(seq):start_idx + (idx+1)*len(seq)]))
#                 self.scores[(start_idx-len(seq)//2) + (idx)*len(seq):(start_idx-len(seq)//2) + (idx+1)*len(seq)] = rev_score[:self.pattern_length]
#             else:
#                 if score > selected_th:
#                     tmp_score = backward_anomaly(self.ts[start_idx + (idx-1)*len(seq):start_idx + (idx+1)*len(seq)], self.pattern_length, selected_nm.subseq, self.normalize)
#                     tmp_score = tmp_score/selected_th
#                     if len(self.scores[start_idx + idx*len(seq):start_idx + (idx+1)*len(seq)]) < len(tmp_score):
#                         tmp_len = len(self.scores[start_idx + idx*len(seq):start_idx + (idx+1)*len(seq)])
#                         self.scores[start_idx + idx*len(seq):start_idx + (idx+1)*len(seq)] = tmp_score[:tmp_len]
#                     else:                        
#                         self.scores[start_idx + idx*len(seq):start_idx + (idx+1)*len(seq)] = tmp_score
#                     before_status = True
#                 else:
#                     if before_status:
#                         tmp_score = backward_anomaly(self.ts[start_idx + (idx-1)*len(seq):start_idx + (idx+1)*len(seq)], self.pattern_length, selected_nm.subseq, self.normalize)
#                         tmp_score = tmp_score/selected_th
#                         if len(self.scores[start_idx + idx*len(seq):start_idx + (idx+1)*len(seq)]) < len(tmp_score):
#                             tmp_len = len(self.scores[start_idx + idx*len(seq):start_idx + (idx+1)*len(seq)])
#                             self.scores[start_idx + idx*len(seq):start_idx + (idx+1)*len(seq)] = tmp_score[:tmp_len]
#                         else:
#                             self.scores[start_idx + idx*len(seq):start_idx + (idx+1)*len(seq)] = tmp_score
#                     else:
#                         tmp_len = len(self.scores[start_idx + idx*len(seq):start_idx + (idx+1)*len(seq)])
#                         self.scores[start_idx + idx*len(seq):start_idx + (idx+1)*len(seq)] = np.ones(tmp_len)*score/selected_th
#                     before_status=False
#
#            if added == 'new':
#                ## -1: newly added NM
#                m_t, d_t = membership(movingWin.NM[-1].subseq, seq, movingWin.NM[-1].tau, eta=1)
#                # self.mem_nm[-1] = np.append(self.mem_nm[-1], movingWin.mem[-1]) 
#                # self.dist_nm[-1] = np.append(self.dist_nm[-1], movingWin.dist[-1]) 
#                self.mem_nm[-1] = np.append(self.mem_nm[-1], m_t) 
#                self.dist_nm[-1] = np.append(self.dist_nm[-1], d_t)
        
        # if added == 'new':
            # print(f'[NEW_NM]: {len(self.mem_nm[-1])} vs. {len(self.mem_nm[0])}')

        # print('AFTER: ', len(self.scores), (start_idx+self.pattern_length//2))

    #  @params seqs: divided subsequences
    #  @params step: step for dividing subsequences
    #  @params overlap: overlap of dividing (i.e., 0: no overlap)
    #  @params NMs: current Normal Model
    def add_new_NM(self, t_seq, step, overlap, NMs, idx):
        """
        Try to add new normal model online 
        """
        ## merging sequences in the window
        # t_seq = np.array([])
        # for seq in seqs: t_seq = np.append(t_seq, seq)

        curr_len, chk_len = self.pattern_length, find_length(t_seq[::-1])

        # if abs(curr_len - chk_len) / curr_len < 0.05: chk_len = curr_len  ## less than 5%
        # elif chk_len <= curr_len/2: chk_len = curr_len
        # elif chk_len >= curr_len*2: chk_len = curr_len

        # if chk_len != curr_len: print('NEW_LEN: ', chk_len)

        chk_len = curr_len

        ## divide sequences with the new chk_len
        # win_seqs = divide_subseq(rev_seq, chk_len, step, overlap)
        win_seqs = divide_subseq(t_seq, chk_len, step, 0)
        win_seqs_n = []
        for seq in win_seqs: win_seqs_n.append(norm_seq(seq, self.normalize))
        win_seqs_n = np.array(win_seqs_n)
        # print('LEN of CHK:', chk_len, 'LEN of SEQ:', len(seqs), len(seqs[0]), len(win_seqs), len(win_seqs[0]))
        listcluster, Z, m_subseq, m_tau, m_nu, _, _, d_ci, d_c_std, _, _ = adaptive_ahc(win_seqs_n, linkage_method='ward', th_reverse=10, kadj=1, eta=self.eta, max_W = self.max_W, isTrain=False, NMs=NMs)

        if listcluster is None: return None, None, None

        ## number of members for each cluster
        nums, new_NM = [], []
        for i in range(int(max(listcluster)+1)): nums.append(len([k for k in listcluster if k==i]))
        # print('Result of AHC:', set(listcluster), nums, len(m_subseq), '# Seq: ', len(seqs))

        j = 0
        for m_s, m_tau, m_nu, m_m, m_std in zip(m_subseq, m_tau, m_nu, d_ci, d_c_std):
            chk = True
            for nm_i, nm in enumerate(NMs):
                ## To resolve align error
                temp_dist1 = np.linalg.norm(compute_diff_dist(nm.subseq, m_s[:len(nm.subseq)//2]))
                temp_dist2 = np.linalg.norm(compute_diff_dist(nm.subseq, m_s[len(nm.subseq)//2:]))
                temp_dist = (temp_dist1+temp_dist2) #* (curr_len/chk_len)
                # print('COMPARE DIST:', nm_i, 'with', temp_dist, 'tau:', nm.tau, 'nu:', nm.nu)

                ## If new m_subseq. is similar to current NM, update tau instead of adding it
                if temp_dist <= nm.tau:
                    ## Update selected NM (status) and tau
                    # print('[Update] :', nm_i, 'with', temp_dist, 'tau:', nm.tau, 'nu:', nm.nu, nm.active, 'num:', nums[j])
                    if nm.active == False:
                        nm.set_active(True)
                        print(f'[--> Active2]: NM {nm_i} from exam. at {idx}')
                        # nm.tau = (nm.tau + m_tau)/2
                        nm.nu = (nm.nu + m_nu)/2
                        # print(f'[Revised] tau: {nm.tau}, nu: {nm.nu}')

                    nums[j] = 0
                    chk = False
                    # print(f'[{j}] Similar to NM {nm_i}/{len(NMs)}: {temp_dist} < {nm.tau}, NUMS: {nums}, {temp_dist1}+{temp_dist2}')
                    break
                # else:
                    # print(f'[{j}] NOT Similar to NM {nm_i}/{len(NMs)}: {temp_dist} > {nm.tau}, NUMS: {nums}')
                
            # if m_nu < np.mean([nm.nu for nm in NMs]):
            if m_nu < np.min([nm.nu for nm in NMs]):
                # print(f'[CHK NU]: new {m_nu} vs. curr {np.min([nm.nu for nm in NMs])}')
                chk = False
                nums[j] = 0
            elif chk:
                ## add candidate NM
                new_NM.append(NormalModel(m_s, m_tau, m_nu, m_m, m_std, active=True))
            j +=1

        for j in range(len(nums)-1, -1, -1): 
            if nums[j] == 0: del nums[j]
        # print('After removing similar ones:', nums, len(new_NM))

        if len(new_NM) >0:
            # plt.figure(figsize=(20,6))
            # for j, nm in enumerate(NMs):
                # if nm.active:
                    # plt.plot(nm.subseq, label=f'ORG {j}')
            # plt.legend()
            # plt.show()

            new_n = []
            # plt.figure(figsize=(20,6))
            for j, nm in enumerate(new_NM):
                # plt.plot(nm.subseq, label=f'New {j, nums[j]}')
                new_n.append(nm.subseq)
            # plt.title('Possible New Normal Models')
            # plt.legend()
            # plt.show()

            d_m = distance.squareform(distance.pdist(new_n))
            # print(d_m)
            if np.max(nums) == 0:
                return None, None, None
            else:
                # print(f'New NMs: # {nums}, tau: {new_NM[np.argmax(m_nu)].tau}, nu: {new_NM[np.argmax(m_nu)].nu}')
                return new_NM[np.argmax(m_nu)], d_m, chk_len
                # return new_NM[int(np.argmax(nums))], d_m, chk_len
        else:
            return None, None, None

