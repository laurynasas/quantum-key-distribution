'''
Created on Mar 1, 2016

@author: laurynas
'''
""" The UIUC/NCSA license:

Copyright (c) 2014 Kwiat Quantum Information Group
All rights reserved.

Developed by:    Kwiat Quantum Information Group
                University of Illinois, Urbana-Champaign (UIUC)
                http://research.physics.illinois.edu/QI/Photonics/

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal with the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimers.
Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimers
in the documentation and/or other materials provided with the distribution.

Neither the names of Kwiat Quantum Information Group, UIUC, nor the names of its contributors may be used to endorse
or promote products derived from this Software without specific prior written permission.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE 
WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE CONTRIBUTORS
OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR 
OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS WITH THE SOFTWARE.
"""

"""

"""

from numpy import *
import numpy
from matplotlib import *
from multiprocessing import Pool
from scipy.optimize import curve_fit
from scipy.misc import factorial
import ttag
import sys
from scipy.weave import inline
#import graphs
from SW_prep import *
from SlepianWolf import *
from entropy_calculator import *
from itertools import *


#Assumes that the person's data is ordered

def create_binary_string_from_laser_pulses(timetags, binsize = 263.15, relative_unit = 78.125):

    # change to int if possible (binsize / relative unit because laser frequency is 3.8HGz)
    BINSIZE = around(binsize/relative_unit)
    number_of_timetags = len(timetags)
    bin_string = zeros(number_of_timetags,dtype=uint64)


    for i in range(number_of_timetags):
        bin_number = around(timetags[i] / BINSIZE)
        bin_string[i]+=bin_number

    '''
    NOTE: If performance is really bad try fixing code below for implementation in low-level language
    '''
# 
#     code = """
#         long long z = 0;
#         long long bin_number = 0;
#         for (;z<number_of_timetags;z++) {
#             bin_number = round(timetags[z] / BINSIZE);
#             bin_string[bin_number] +=1;
#         }
#     """
#     inline(code,["BINSIZE","bin_string","timetags","number_of_timetags"],headers=["<math.h>"])

    return bin_string

def log2_modified(x):
    # if letter probability is 0 returns 0
    if x > 0:
        return numpy.log2(x)
    return 0

def get_size_of_alphabet(frame_size):
    # generates frame size binary string with 1 (maximum alphabet value) and converts it to integer
    return int('1'*frame_size, 2)

def letter_probabilities(frame_locations, size_of_alphabet):
    probabilities = zeros(size_of_alphabet)
    for letter in xrange(size_of_alphabet):
        # Counts occurences of the particular mapping value (letter) in the frame_locations array

        probabilities[letter] = sum(frame_locations == letter)
        # print "Letter (binary string): ", letter, " has probability: ", probabilities[letter] / len(frame_locations)

    # divides by total number  of entries to obtain probability
    probabilities /= len(frame_locations)
    return probabilities

def get_binomial_coefficient(frame_size, letter):
    return float(factorial(frame_size)/(factorial(letter)*factorial(frame_size-letter)))

def letter_probabilities_using_occupancy(frame_occupancies, frame_size):
    number_of_ones = sum(frame_occupancies)
    length_of_binary_string = len(frame_occupancies) * frame_size
    probability_one = number_of_ones / length_of_binary_string
    probability_zero = 1 - probability_one

    '''
     as by increasing frame we increase the amount of ones that can be stored inside
     (i.e. 10 can store 2 ones max and 100 can store 3 ones max)
    '''

    size_of_alphabet = frame_size
    probabilities = zeros(size_of_alphabet)
    # print "Probability of one: ", probability_one
    # print "Probability of zero: ", probability_zero
    
    for letter in xrange(size_of_alphabet):
        # Counts probability of particular occupancy to occur (i.e. 1100 == 0011 == 0101 ==1010 == 0110 == 1001)
        probabilities[letter] = ((probability_one**letter)*(probability_zero**(frame_size-letter))) * get_binomial_coefficient(frame_size, letter)
        # print "Letter (occupancy): ", letter, " has probability: ", probabilities[letter]
    # divides by total number  of entries to obtain probability
    return probabilities

def calculate_frame_entropy_using_occupancy(frame_occupancies, frame_size):
    entropy = 0
    size_of_alphabet = frame_size + 1
    probabilities = letter_probabilities_using_occupancy(frame_occupancies, frame_size+1)
    for i in xrange(size_of_alphabet):
        entropy += probabilities[i]*log2_modified(probabilities[i])
    return entropy*(-1)  

def calculate_frame_entropy(frame_locations, frame_size):
    entropy = 0
    size_of_alphabet = get_size_of_alphabet(frame_size) + 1 
    probabilities = letter_probabilities(frame_locations, size_of_alphabet)
    for i in xrange(size_of_alphabet):
        entropy += probabilities[i]*log2_modified(probabilities[i])
    return entropy*(-1)

def calculate_frame_occupancy(binary_string, frame_size):

    number_of_frames = around(binary_string[-1]/frame_size + 1)
    # print "Total number of frames: ", number_of_frames
    frame_occupancy = zeros(int(number_of_frames),dtype=uint16)
    
    for event_index in binary_string:
        frame_occupancy[int(event_index)/frame_size] +=1    
        
    return frame_occupancy

'''
TO DO: Test manually first!!!! NEW: Passes simple tests
'''
def calculate_frame_locations(binary_string, frame_occupancies, frame_size):
    number_of_frames = len(frame_occupancies)
    frame_locations = zeros(number_of_frames,dtype=uint32)
    iterator = binary_string.__iter__()
    i=-1
    for element in iterator:
        i+=1
        # print "------------new iteration------------------"
        map_value = 0
        frame_number = int(element/frame_size)
        # print "Frame number is: ", frame_number 
        position_in_frame = element%frame_size
        # print "Position in frame is: ", position_in_frame
        binary_position = frame_size - position_in_frame - 1
        # print "Binary position: ", binary_position
        map_value +=2**binary_position
        # print "Map value: ", map_value
        # to iterate through remaining elements in the frame
        for j in range (int(position_in_frame+1), frame_size):
            # print "position of element to be checked: ",(frame_number*frame_size+j)
            if (frame_number*frame_size+j) in binary_string  :
                # print "more elements to find"
                # print "degree of remaining",frame_size-j-1
                map_value +=2**(frame_size-j-1)
                iterator.next()
            else:
                continue
        frame_locations[frame_number] = map_value
        # print "Final map value: ", map_value
    return frame_locations

def calculate_frame_locations_daniels_mapping(binary_string,frame_occupancies, frame_size):
    number_of_frames = len(frame_occupancies)
    frame_locations = zeros(number_of_frames,dtype=uint32)
    number_of_timetags = len(binary_string)
    frame_numbers = binary_string.copy()
    frame_numbers /= frame_size

    for i in range(number_of_timetags):
        mapping_value = 0
        frame_number = frame_numbers[i]
        mapping_value = (binary_string[i] % frame_size) * (frame_size**(frame_occupancies[frame_number]-1))
        frame_locations[frame_number] += mapping_value

    return frame_locations

def make_data_string_same_size(alice_string, bob_string):
    if (len(alice_string) > len(bob_string)):
        alice_string    = alice_string[:len(bob_string)]
    else:
        bob_string    = bob_string[:len(alice_string)]
    return (alice_string, bob_string)

def createLDPCdata(timetags,polarizations,total_number_of_frames=None,frame_size=16):
    frame_numbers = timetags.copy()
    frame_numbers /= frame_size
    #Get the number of time bins
    if (total_number_of_frames == None): total_number_of_frames = frame_numbers[-1]+1

    #Create an array for the frame occupancy and location sequences
    frame_occupancy = zeros(total_number_of_frames,dtype=uint32)
    frame_location = zeros(total_number_of_frames,dtype=uint64)
    person_p = zeros(total_number_of_frames,dtype=uint8)
    frame_size = int(frame_size)

    # print("Frame numbers: ", frame_numbers)
    number_of_timetags = int(argmax(frame_numbers>total_number_of_frames))
    if (number_of_timetags==0 and frame_numbers[0] > total_number_of_frames):
        print "ERROR: TOT is smaller than minvalue!"
        return None
    if (number_of_timetags==0):
        number_of_timetags = int(len(timetags))
    
    maxtag = (timetags[number_of_timetags-1])
    # print("total number of frames: ",total_number_of_frames)

    code = """
        long long z = 0;
        for (;z<number_of_timetags;z++) {
            frame_occupancy[frame_numbers[z]] +=1;
            frame_location[frame_numbers[z]] += (timetags[z] % frame_size)*(pow((double)frame_size,(double)(frame_occupancy[frame_numbers[z]]-1)));
            person_p[frame_numbers[z]] = polarizations[z];
        }
    """
    inline(code,["frame_occupancy","frame_location","person_p","frame_numbers","polarizations","timetags","number_of_timetags","frame_size"],headers=["<math.h>"])

    # frame location counts how many occurances there are in the frame
    """
    for z in xrange(len(timetags)):
        frame_occupancy[frame_numbers[z]] += 1
        frame_location[frame_numbers[z]] = (timetags[z] % frame_size) * frame_occupancy[frame_numbers[z]]*frame_size
        person_p[frame_numbers[z]] = polarizations[z]
    """
    return (frame_occupancy,frame_location,person_p,maxtag)


#Assumes the timetags's data is ordered
def createBdata(person,tot=None):
    
    sw_p=person.copy()
    
    if (tot==None): tot=sw_p[-1]+1
    
    person_sw=zeros(tot,dtype=bool)
    
    doublenum=0
    for z in xrange(len(person)):
        #There is no value here, so save the value
        person_sw[sw_p[z]]=True
    
    return person_sw

def bincoincidences(A,B,pm=26):
    A=A.copy()
    B=B.copy()
    
    #Subtract the smallest time bin
    if (A[0]<=B[0]):
        A[:]-=A[0]-pm
        B[:]-=A[0]-pm
    else:
        A[:]-=B[0]-pm
        B[:]-=B[0]-pm
    
    #Split into time bins
    A/=pm*2
    B/=pm*2
    
    #Find coincidences
    coincidence = 0
    
    return len(intersect1d(A,B))

def binData(bufAlice,binsize):
    channels,timetags = bufAlice[:]
    timetags +=binsize/2-timetags[0]
    timebins = around(timetags/binsize).astype(uint64)
    timebins -= timebins[0] #zero the time bins
    return (channels,timebins)

def extractAliceBob(c,t,aliceChannels,bobChannels):
    bobmask = (c==bobChannels[0])
    for i in range(1,len(bobChannels)):
        bobmask = logical_or(bobmask,c==bobChannels[i])
    alicemask = (c == aliceChannels[0])
    for i in range(1,len(aliceChannels)):
        alicemask = logical_or(alicemask,c==aliceChannels[i])

    bob = t[bobmask]
    alice = t[alicemask]

    bob_pol = c[bobmask]
    alice_pol  = c[alicemask]

    #Reset the polarization detectors
    for i in range(len(aliceChannels)):
        alice_pol[alice_pol==aliceChannels[i]]=i
    for i in range(len(bobChannels)):
        bob_pol[bob_pol==bobChannels[i]]=i

    return (bob,alice,bob_pol,alice_pol)


def prep():
    #Alice and Bob Channels
    aliceChannels=[0,1,2,3]
    bobChannels=[4,5,6,7]

    #binsize: The time in seconds of a bin
    binsize = 1/(32*120.0e6)

    #Create the buffer that will do stuff
    bufAlice = ttag.TTBuffer(1)

    print("Binning...")

    #The time allocated to each bin:
    c,t = binData(bufAlice,binsize)

    #Create data sequences for Alice and Bob
    bob,alice,bob_pol,alice_pol = extractAliceBob(c,t,aliceChannels,bobChannels)

    print("Finding Intersect")
    #Make sure Alice and Bob datasets coencide
    aliceMask = logical_and(alice > bob[0],alice < bob[-1])
    bobMask = logical_and(bob > alice[0],bob < alice[-1])

    bob = bob[bobMask]
    bob_pol = bob_pol[bobMask]
    alice = alice[aliceMask]
    alice_pol = alice_pol[aliceMask]

    #Now, rezero
    z = min(bob[0],alice[0])

    bob-=z
    alice-=z

    return (alice,bob,alice_pol,bob_pol)


def saveprep(fname,alice,bob,alice_pol,bob_pol):
    print("Saving Data Arrays")
    sys.stdout.flush()
    save("./results/results/alice_"+fname+".npy",alice)
    save("./results/results/bob_"+fname+".npy",bob)
    save("./results/results/alice_pol_"+fname+".npy",alice_pol)
    save("./results/results/bob_pol_"+fname+".npy",bob_pol)

def loadprep(fname):
    print("Loading Alice and Bob arrays")

    sys.stdout.flush()
    alice = load("./resultsLaurynas/aliceTtags_"+fname+".npy")
    bob = load("./resultsLaurynas/bobTtags_"+fname+".npy")
    alice_pol=load("./resultsLaurynas/aliceChannels_"+fname+".npy")
    bob_pol = load("./resultsLaurynas/bobChannels_"+fname+".npy")

    return (alice,bob,alice_pol,bob_pol)

def resequence1(location_value,frame_size,occupancy,actual_binary_string_bool=None,frame_offset=0):
    # Larry: Nonsense... actual_binary_string_bool size == timetag size (why'd you create size of alphabet??)
    # if (actual_binary_string_bool==None):
    #     actual_binary_string_bool = zeros(frame_size,dtype=bool)
     
    # actual mapping: (binary_string[i] % frame_size) * (frame_size**(frame_occupancies[frame_number]-1))
    # high level translation: (position of 1 in frame) * (frame_size^(that_frame_occupancy - 1)) 
    # For frame occ of 1 (most likely): location value would simply be its position in frame
    # For frame occ of 2:               location value would simply be its occupancy(i.e. 2)*(position in frame*(frame_size))\

    # occupancy of particual frame (usually 1)
    for i in range(occupancy):
        # position of 1 in laser binary string (as location value in case of occ 1 is just position in frame)
        actual_binary_string_bool[frame_offset+location_value%frame_size] = True
        # why would you do this?? this is local variable and is not used anywhere
        location_value=location_value/frame_size

    # returns boolean array of actual binary string (1s and 0s) size with true in places where 1 occurs in laser binary string
    return actual_binary_string_bool

def resequence(locations,occupancies,frame_size):
    # create array of actual binary string length
    actual_binary_string_bool = zeros(frame_size*len(locations),dtype=bool)
    for i in xrange(len(locations)):
        # originally wasn't assigning new value to actual_binary_string_bool
        actual_binary_string_bool = resequence1(locations[i],frame_size,occupancies[i],actual_binary_string_bool,frame_size*i)
    return actual_binary_string_bool


def calculateStatistics(alice,bob,alice_pol,bob_pol):
    #saveprep("main_high",*prep())
    numpy.set_printoptions(edgeitems = 100) 
    

    alice_binary_string_laser = create_binary_string_from_laser_pulses(alice)
    bob_binary_string_laser = create_binary_string_from_laser_pulses(bob)

    #Create the LDPC arrays (range 1-13)
    for frame_size in 2**array(range(1,13)):
        print "\n"
        print("DOING ALPHABET",frame_size)
        # totlen = 8000000#min(max(int(alice[-1]/16),int(bob[-1]/16)),500000000)
        print("Extracting Data")
        
        # can test frame_location algorithm with following line
        # print calculate_frame_locations(array([0,1,2,3,4,5,6,7,8,9,10,11,12]), array([4,4,4,1]), 4)

        # Old implementation
        # (bob_frame_occupancies,bob_frame_locations,bob_p,maxtag_b) = createLDPCdata(bob,bob_pol,total_number_of_frames = totlen,frame_size=frame_size)

        print "Calculating frame occupancies..."
        alice_frame_occupancies = calculate_frame_occupancy(alice_binary_string_laser, frame_size)
        bob_frame_occupancies   = calculate_frame_occupancy(bob_binary_string_laser,frame_size)

        print("Calculating frame locations...")

        # alice_frame_locations = calculate_frame_locations(alice_binary_string_laser, alice_frame_occupancies, frame_size)
        # bob_frame_locations = calculate_frame_locations(bob_binary_string_laser,bob_frame_occupancies,frame_size)
        # print "Entropy using frame mapping: "
        # print calculate_frame_entropy(alice_frame_locations, frame_size)


        # not binary mapping_value but calculates way faster
        alice_frame_locations = calculate_frame_locations_daniels_mapping(alice_binary_string_laser, alice_frame_occupancies, frame_size)
        bob_frame_locations   = calculate_frame_locations_daniels_mapping(bob_binary_string_laser,bob_frame_occupancies,frame_size)

        (alice_frame_occupancies,bob_frame_occupancies) = make_data_string_same_size(alice_frame_occupancies,bob_frame_occupancies)
        (alice_frame_locations,bob_frame_locations) = make_data_string_same_size(alice_frame_locations,bob_frame_locations)
        print ("Making data sizes the same for both Bob and Alice...All equal? ", len(alice_frame_occupancies)
                                                                                 ==len(bob_frame_occupancies)
                                                                                 ==len(alice_frame_locations)
                                                                                 ==len(bob_frame_locations))

        print "Entropy using frame occupancy: ", calculate_frame_entropy_using_occupancy(alice_frame_occupancies, frame_size)


        sys.stdout.flush()
    
        # ------------------------DEALS WITH OCCUPANCIES > 1 ------------------------------------------------------------
        # #2-1,2-2,etc:
        # calculates where at least one of them has higher occupancy than one
        occupancy_grater_than_one = logical_or(alice_frame_occupancies>1,bob_frame_occupancies>1)

        # takes frames which were non zero either in alice or bob data
        alice_potential_non_zero_locations = alice_frame_locations[occupancy_grater_than_one]
        bob_potential_non_zero_locations = bob_frame_locations[occupancy_grater_than_one]

        alice_occupancy_greater_than_one = alice_frame_occupancies[occupancy_grater_than_one]
        bob_occupancy_greater_than_one = bob_frame_occupancies[occupancy_grater_than_one]

        multibob = resequence(bob_potential_non_zero_locations,bob_occupancy_greater_than_one,frame_size)
        multialice = resequence(alice_potential_non_zero_locations,alice_occupancy_greater_than_one,frame_size)
        #-----------------------------------------------------------------------------------------------------------------

        # #1-1,etc

        mutual_frames_with_occupancy_one = logical_and(alice_frame_occupancies==1,bob_frame_occupancies==1)
    
        alice_non_zero_positions_in_frame = alice_frame_locations[mutual_frames_with_occupancy_one]
        bob_non_zero_positions_in_frame   = bob_frame_locations[mutual_frames_with_occupancy_one]
    
        # ------------------Polarizations of nonzero elements ------------------------------------------------------------
        # alice_pf = alice_p[mutual_frames_with_occupancy_one]
        # bob_pf = bob_p[mutual_frames_with_occupancy_one]
        # ----------------------------------------------------------------------------------------------------------------

        print "Alice and Bob frame location DATA saved for LDPC procedure."
        # fmt="%i" saves signed decimal integers
        # sample should look like for frame size 4:
        #   ALICE: [0,1,2,2,3]
        #   BOB:   [0,1,2,2,4] <-- error in last element 
        # saves the last one frame size
        savetxt("./resultsLaurynas/ALICE_BOB_NON_ZERO_POSITIONS_IN_FRAME.csv",(alice_non_zero_positions_in_frame,bob_non_zero_positions_in_frame),fmt="%i")

        # #graphs.polarizationPlot(alice_pf,bob_pf)

        #Extract code statistics


        print "->Code statistics: "
        sys.stdout.flush()
    
        print "Frame Occupancy: "
        print "\tLength:",len(bob_frame_occupancies)
        occ_number_of_coincidences = sum(bob_frame_occupancies==alice_frame_occupancies)
        occ_coincidence_fraction = float(occ_number_of_coincidences)/len(bob_frame_occupancies)
        print "\tNumber of coincidences:",occ_number_of_coincidences," with fraction of: ",occ_coincidence_fraction
        print "\tError:",1-occ_coincidence_fraction
    
        print "Frame Location: "
        print "\tLength:",len(bob_non_zero_positions_in_frame)
        loc_number_of_coincidences = sum(alice_non_zero_positions_in_frame==bob_non_zero_positions_in_frame)
        loc_coincidence_fraction = float(loc_number_of_coincidences)/len(bob_non_zero_positions_in_frame)
        print "\tNumber of coincidences:",loc_number_of_coincidences,loc_coincidence_fraction
        print "\tError:",1-loc_coincidence_fraction



        # The probability of a 1 in the original-original sequence
        p1 = float(len(alice))/alice[-1]
        print "probability of 1 for Alice:",p1," and Bob: ",float(len(bob))/bob[-1]
    
        same_timetags_for_both = intersect1d(alice,bob)
        p1g1 = float(len(same_timetags_for_both))/len(alice)
        print "Coincidence rate (p1g1) for Alice: ",p1g1," and Bob: ",float(len(same_timetags_for_both))/len(bob)

        if (any(alice_frame_occupancies > frame_size) or any(bob_frame_occupancies > frame_size)):
            # NOTE: would be better just to raise the error and terminate the process rather than artificially modify data
            print "WARNING: Over the TOP!"
            alice_frame_occupancies[alice_frame_occupancies >= frame_size]=frame_size-1
            bob_frame_occupancies[bob_frame_occupancies >= frame_size]=frame_size-1
        sys.stdout.flush()

        swtransmat = transitionMatrix_data2(alice_frame_occupancies,bob_frame_occupancies,frame_size)
        alice_occ_letter_probabilities = letter_probabilities(alice_frame_occupancies,frame_size)
        
        print "Calucalting Letter Probabilities:"
        # print alice_occ_letter_probabilities
        print "Calculating Transition Matrix (SW):"
        # print swtransmat
        nbtransmat = transitionMatrix_data2(alice_non_zero_positions_in_frame,bob_non_zero_positions_in_frame,frame_size)
        nbpl = letter_probabilities(alice_non_zero_positions_in_frame,frame_size)
        print "Calculating Letter Probabilities:"
        # print nbpl
        print "Calculating Transition Matrix (NB):"
        # print nbtransmat
        maxtag_a = alice[-1]
        # #The total number of original bins is alice, and the final bits is the number of nonbinary left
        nb_bperf= maxtag_a/len(bob_non_zero_positions_in_frame)
        print "Number of original bits per nonbinary:",nb_bperf


        # #2-x theory
        multi_c = float(sum(logical_and(multialice,multibob)))
        multi_p1b = float(sum(multibob))/float(len(multibob))
        multi_p1g1b = multi_c/float(sum(multibob))
        multi_p1a = float(sum(multialice))/float(len(multialice))
        if(sum(multialice)!=0):
            multi_p1g1a = multi_c/float(sum(multialice))
        else:
            multi_p1g1a = multi_c/float(1)
        multi_bperf = maxtag_a/float(len(multibob))
        print "MULTI"
        print "Length:",len(multibob)
        print "Ones:",sum(multibob),sum(multialice)
        print "Coincidences",multi_c
        print "p1",multi_p1b,multi_p1a
        print "p1g1",multi_p1g1b,multi_p1g1a
        print "Number of original bits per multi:",multi_bperf
        entropy_left = theoretical(multi_p1a,multi_p1g1a,multi_p1b,multi_p1g1b)
        multientropy = entropy_left/multi_bperf
        
        p1_bob = float(len(bob))/bob[-1]
        print ("alice vs bob: ",p1,p1_bob)
        (te,te2,be,nbe)=entropy_calculate2(p1,p1g1,p1_bob,p1g1,frame_size,alice_occ_letter_probabilities,swtransmat,nb_bperf,nbpl,nbtransmat)
        f=open("resultsLaurynas/entropy_1","a")
        f.write(str(frame_size)+" "+str(te)+" "+str(te2)+" "+str(be)+" "+str(nbe) +" "+str(multientropy)+"\n")
        f.close()