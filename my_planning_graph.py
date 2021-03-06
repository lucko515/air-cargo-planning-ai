from aimacode.planning import Action
from aimacode.search import Problem
from aimacode.utils import expr
from lp_utils import decode_state


class PgNode():
    """Base class for planning graph nodes.

    includes instance sets common to both types of nodes used in a planning graph
    parents: the set of nodes in the previous level
    children: the set of nodes in the subsequent level
    mutex: the set of sibling nodes that are mutually exclusive with this node
    """

    def __init__(self):
        self.parents = set()
        self.children = set()
        self.mutex = set()

    def is_mutex(self, other) -> bool:
        """Boolean test for mutual exclusion

        :param other: PgNode
            the other node to compare with
        :return: bool
            True if this node and the other are marked mutually exclusive (mutex)
        """
        if other in self.mutex:
            return True
        return False

    def show(self):
        """helper print for debugging shows counts of parents, children, siblings

        :return:
            print only
        """
        print("{} parents".format(len(self.parents)))
        print("{} children".format(len(self.children)))
        print("{} mutex".format(len(self.mutex)))


class PgNode_s(PgNode):
    """A planning graph node representing a state (literal fluent) from a
    planning problem.

    Args:
    ----------
    symbol : str
        A string representing a literal expression from a planning problem
        domain.

    is_pos : bool
        Boolean flag indicating whether the literal expression is positive or
        negative.
    """

    def __init__(self, symbol: str, is_pos: bool):
        """S-level Planning Graph node constructor

        :param symbol: expr
        :param is_pos: bool
        Instance variables calculated:
            literal: expr
                    fluent in its literal form including negative operator if applicable
        Instance variables inherited from PgNode:
            parents: set of nodes connected to this node in previous A level; initially empty
            children: set of nodes connected to this node in next A level; initially empty
            mutex: set of sibling S-nodes that this node has mutual exclusion with; initially empty
        """
        PgNode.__init__(self)
        self.symbol = symbol
        self.is_pos = is_pos
        self.__hash = None

    def show(self):
        """helper print for debugging shows literal plus counts of parents,
        children, siblings

        :return:
            print only
        """
        if self.is_pos:
            print("\n*** {}".format(self.symbol))
        else:
            print("\n*** ~{}".format(self.symbol))
        PgNode.show(self)

    def __eq__(self, other):
        """equality test for nodes - compares only the literal for equality

        :param other: PgNode_s
        :return: bool
        """
        return (isinstance(other, self.__class__) and
                self.is_pos == other.is_pos and
                self.symbol == other.symbol)

    def __hash__(self):
        self.__hash = self.__hash or hash(self.symbol) ^ hash(self.is_pos)
        return self.__hash


class PgNode_a(PgNode):
    """A-type (action) Planning Graph node - inherited from PgNode """


    def __init__(self, action: Action):
        """A-level Planning Graph node constructor

        :param action: Action
            a ground action, i.e. this action cannot contain any variables
        Instance variables calculated:
            An A-level will always have an S-level as its parent and an S-level as its child.
            The preconditions and effects will become the parents and children of the A-level node
            However, when this node is created, it is not yet connected to the graph
            prenodes: set of *possible* parent S-nodes
            effnodes: set of *possible* child S-nodes
            is_persistent: bool   True if this is a persistence action, i.e. a no-op action
        Instance variables inherited from PgNode:
            parents: set of nodes connected to this node in previous S level; initially empty
            children: set of nodes connected to this node in next S level; initially empty
            mutex: set of sibling A-nodes that this node has mutual exclusion with; initially empty
        """
        PgNode.__init__(self)
        self.action = action
        self.prenodes = self.precond_s_nodes()
        self.effnodes = self.effect_s_nodes()
        self.is_persistent = self.prenodes == self.effnodes
        self.__hash = None

    def show(self):
        """helper print for debugging shows action plus counts of parents, children, siblings

        :return:
            print only
        """
        print("\n*** {!s}".format(self.action))
        PgNode.show(self)

    def precond_s_nodes(self):
        """precondition literals as S-nodes (represents possible parents for this node).
        It is computationally expensive to call this function; it is only called by the
        class constructor to populate the `prenodes` attribute.

        :return: set of PgNode_s
        """
        nodes = set()
        for p in self.action.precond_pos:
            nodes.add(PgNode_s(p, True))
        for p in self.action.precond_neg:
            nodes.add(PgNode_s(p, False))
        return nodes

    def effect_s_nodes(self):
        """effect literals as S-nodes (represents possible children for this node).
        It is computationally expensive to call this function; it is only called by the
        class constructor to populate the `effnodes` attribute.

        :return: set of PgNode_s
        """
        nodes = set()
        for e in self.action.effect_add:
            nodes.add(PgNode_s(e, True))
        for e in self.action.effect_rem:
            nodes.add(PgNode_s(e, False))
        return nodes

    def __eq__(self, other):
        """equality test for nodes - compares only the action name for equality

        :param other: PgNode_a
        :return: bool
        """
        return (isinstance(other, self.__class__) and
                self.is_persistent == other.is_persistent and
                self.action.name == other.action.name and
                self.action.args == other.action.args)

    def __hash__(self):
        self.__hash = self.__hash or hash(self.action.name) ^ hash(self.action.args)
        return self.__hash


def mutexify(node1: PgNode, node2: PgNode):
    """ adds sibling nodes to each other's mutual exclusion (mutex) set. These should be sibling nodes!

    :param node1: PgNode (or inherited PgNode_a, PgNode_s types)
    :param node2: PgNode (or inherited PgNode_a, PgNode_s types)
    :return:
        node mutex sets modified
    """
    if type(node1) != type(node2):
        raise TypeError('Attempted to mutex two nodes of different types')
    node1.mutex.add(node2)
    node2.mutex.add(node1)


class PlanningGraph():
    """
    A planning graph as described in chapter 10 of the AIMA text. The planning
    graph can be used to reason about 
    """

    def __init__(self, problem: Problem, state: str, serial_planning=True):
        """
        :param problem: PlanningProblem (or subclass such as AirCargoProblem or HaveCakeProblem)
        :param state: str (will be in form TFTTFF... representing fluent states)
        :param serial_planning: bool (whether or not to assume that only one action can occur at a time)
        Instance variable calculated:
            fs: FluentState
                the state represented as positive and negative fluent literal lists
            all_actions: list of the PlanningProblem valid ground actions combined with calculated no-op actions
            s_levels: list of sets of PgNode_s, where each set in the list represents an S-level in the planning graph
            a_levels: list of sets of PgNode_a, where each set in the list represents an A-level in the planning graph
        """
        self.problem = problem
        self.fs = decode_state(state, problem.state_map)
        self.serial = serial_planning
        self.all_actions = self.problem.actions_list + self.noop_actions(self.problem.state_map)
        self.s_levels = []
        self.a_levels = []
        self.create_graph()

    def noop_actions(self, literal_list):
        """create persistent action for each possible fluent

        "No-Op" actions are virtual actions (i.e., actions that only exist in
        the planning graph, not in the planning problem domain) that operate
        on each fluent (literal expression) from the problem domain. No op
        actions "pass through" the literal expressions from one level of the
        planning graph to the next.

        The no-op action list requires both a positive and a negative action
        for each literal expression. Positive no-op actions require the literal
        as a positive precondition and add the literal expression as an effect
        in the output, and negative no-op actions require the literal as a
        negative precondition and remove the literal expression as an effect in
        the output.

        This function should only be called by the class constructor.

        :param literal_list:
        :return: list of Action
        """
        action_list = []
        for fluent in literal_list:
            act1 = Action(expr("Noop_pos({})".format(fluent)), ([fluent], []), ([fluent], []))
            action_list.append(act1)
            act2 = Action(expr("Noop_neg({})".format(fluent)), ([], [fluent]), ([], [fluent]))
            action_list.append(act2)
        return action_list

    def create_graph(self):
        """ build a Planning Graph as described in Russell-Norvig 3rd Ed 10.3 or 2nd Ed 11.4

        The S0 initial level has been implemented for you.  It has no parents and includes all of
        the literal fluents that are part of the initial state passed to the constructor.  At the start
        of a problem planning search, this will be the same as the initial state of the problem.  However,
        the planning graph can be built from any state in the Planning Problem

        This function should only be called by the class constructor.

        :return:
            builds the graph by filling s_levels[] and a_levels[] lists with node sets for each level
        """
        # the graph should only be built during class construction
        if (len(self.s_levels) != 0) or (len(self.a_levels) != 0):
            raise Exception(
                'Planning Graph already created; construct a new planning graph for each new state in the planning sequence')

        # initialize S0 to literals in initial state provided.
        leveled = False
        level = 0
        self.s_levels.append(set())  # S0 set of s_nodes - empty to start
        # for each fluent in the initial state, add the correct literal PgNode_s
        for literal in self.fs.pos:
            self.s_levels[level].add(PgNode_s(literal, True))
        for literal in self.fs.neg:
            self.s_levels[level].add(PgNode_s(literal, False))
        # no mutexes at the first level

        # continue to build the graph alternating A, S levels until last two S levels contain the same literals,
        # i.e. until it is "leveled"
        while not leveled:
            self.add_action_level(level)
            self.update_a_mutex(self.a_levels[level])

            level += 1
            self.add_literal_level(level)
            self.update_s_mutex(self.s_levels[level])

            if self.s_levels[level] == self.s_levels[level - 1]:
                leveled = True

    def add_action_level(self, level):
        """ add an A (action) level to the Planning Graph

        :param level: int
            the level number alternates S0, A0, S1, A1, S2, .... etc the level number is also used as the
            index for the node set lists self.a_levels[] and self.s_levels[]
        :return:
            adds A nodes to the current level in self.a_levels[level]
        """
        # TODO add action A level to the planning graph as described in the Russell-Norvig text
        # 1. determine what actions to add and create those PgNode_a objects
        # 2. connect the nodes to the previous S literal level
        # for example, the A0 level will iterate through all possible actions for the problem and add a PgNode_a to a_levels[0]
        #   set iff all prerequisite literals for the action hold in S0.  This can be accomplished by testing
        #   to see if a proposed PgNode_a has prenodes that are a subset of the previous S level.  Once an
        #   action node is added, it MUST be connected to the S node instances in the appropriate s_level set.

        #THE HELP for understaing planning graph I have found in these lessons: https://www.youtube.com/watch?v=YPJ6yMMNx-s

        #So the idea is this: We want to add to the current action layer just actions that can be performed from preconditions specified in the
        #current 'literal level'/S level/preconditions level.
        action_level = []
        #This for loop will list through all actions that can be performed - incloding noop actions.
        for action in self.all_actions:

            #We are getting the list of literals in the looked level
            literals = self.s_levels[level] 
            action_node = PgNode_a(action)
            precond_for_node = action_node.prenodes
            #now to check if all precond for actions are in literals
            # We can check with simple for loop or with function issubset and convert both lists to sets
            if precond_for_node.issubset(literals):

                action_level.append(action_node)

                #Now its time to connect those nodes
                for literal in literals:

                    #So here we are adding to current nodes parents to be all literals in literal layer
                    action_node.parents.add(literal)
                    #and for every literal we are adding new child, which is current node
                    literal.children.add(action_node)
                    #by doing these two operations we are making layers in our planning graph (something like neural network structure)

        self.a_levels.append(action_level)        

    def add_literal_level(self, level):
        """ add an S (literal) level to the Planning Graph

        :param level: int
            the level number alternates S0, A0, S1, A1, S2, .... etc the level number is also used as the
            index for the node set lists self.a_levels[] and self.s_levels[]
        :return:
            adds S nodes to the current level in self.s_levels[level]
        """
        # TODO add literal S level to the planning graph as described in the Russell-Norvig text
        # 1. determine what literals to add
        # 2. connect the nodes
        # for example, every A node in the previous level has a list of S nodes in effnodes that represent the effect
        #   produced by the action.  These literals will all be part of the new S level.  Since we are working with sets, they
        #   may be "added" to the set without fear of duplication.  However, it is important to then correctly create and connect
        #   all of the new S nodes as children of all the A nodes that could produce them, and likewise add the A nodes to the
        #   parent sets of the S nodes

        literal_level = []

        #If we want to calculate what will be our 'preconditions' or elements for next literal level we will need ACTIONS from previous level
        #in our planning graph
        for action in self.a_levels[level - 1]:

            #getting nodes effected by current action [positive and negative]
            current_action_effect = action.effnodes

            #going through states contained in the effected nodes
            for state in current_action_effect:

                #adding those nodes to literal_level variable (which will be our new s_level)
                literal_level.append(state)

                #for creating currect graph we need to connect previous layer/level with a next one
                state.parents.add(action)
                action.children.add(state)

        #because some actions are have same states as the effnodes, we are having duplicates in literal_level
        #so we are adding - set - instead. (Remove all duplicates)
        self.s_levels.append(set(literal_level))

    def update_a_mutex(self, nodeset):
        """ Determine and update sibling mutual exclusion for A-level nodes

        Mutex action tests section from 3rd Ed. 10.3 or 2nd Ed. 11.4
        A mutex relation holds between two actions a given level
        if the planning graph is a serial planning graph and the pair are nonpersistence actions
        or if any of the three conditions hold between the pair:
           Inconsistent Effects
           Interference
           Competing needs

        :param nodeset: set of PgNode_a (siblings in the same level)
        :return:
            mutex set in each PgNode_a in the set is appropriately updated
        """
        nodelist = list(nodeset)
        for i, n1 in enumerate(nodelist[:-1]):
            for n2 in nodelist[i + 1:]:
                if (self.serialize_actions(n1, n2) or
                        self.inconsistent_effects_mutex(n1, n2) or
                        self.interference_mutex(n1, n2) or
                        self.competing_needs_mutex(n1, n2)):
                    mutexify(n1, n2)

    def serialize_actions(self, node_a1: PgNode_a, node_a2: PgNode_a) -> bool:
        """
        Test a pair of actions for mutual exclusion, returning True if the
        planning graph is serial, and if either action is persistent; otherwise
        return False.  Two serial actions are mutually exclusive if they are
        both non-persistent.

        :param node_a1: PgNode_a
        :param node_a2: PgNode_a
        :return: bool
        """
        #
        if not self.serial:
            return False
        if node_a1.is_persistent or node_a2.is_persistent:
            return False
        return True

    def inconsistent_effects_mutex(self, node_a1: PgNode_a, node_a2: PgNode_a) -> bool:
        """
        Test a pair of actions for inconsistent effects, returning True if
        one action negates an effect of the other, and False otherwise.

        HINT: The Action instance associated with an action node is accessible
        through the PgNode_a.action attribute. See the Action class
        documentation for details on accessing the effects and preconditions of
        an action.

        :param node_a1: PgNode_a
        :param node_a2: PgNode_a
        :return: bool
        """
        #Inconsistent effects: an effect of one negates an effect of the other
        #Slides to find more inforumation: University of Maryland https://www.cs.umd.edu/~nau/planning/slides/chapter06.pdf Page/slide: 9
        
        #getting just an action from nodes
        action_a1 = node_a1.action
        action_a2 = node_a2.action

        #to check if there is Inconsistent_effects at those nodes
        #we get actions adding and removing effects
        add_a1 = action_a1.effect_add
        rem_a1 = action_a1.effect_rem

        add_a2 = action_a2.effect_add
        rem_a2 = action_a2.effect_rem

        #Going through adding states from first action
        for add_ in add_a1:
            #if that adding state is in remove states from second action, those 2 actions are mutax
            if add_ in rem_a2:
                return True

        #Going through adding states from second action
        for add_ in add_a2:
            #if that adding state is in remove states from first action, those 2 actions are mutax
            if add_ in rem_a1:
                return True

        return False

    def interference_mutex(self, node_a1: PgNode_a, node_a2: PgNode_a) -> bool:
        """
        Test a pair of actions for mutual exclusion, returning True if the 
        effect of one action is the negation of a precondition of the other.

        HINT: The Action instance associated with an action node is accessible
        through the PgNode_a.action attribute. See the Action class
        documentation for details on accessing the effects and preconditions of
        an action.

        :param node_a1: PgNode_a
        :param node_a2: PgNode_a
        :return: bool
        """
        #Slides to find more inforumation: University of Maryland https://www.cs.umd.edu/~nau/planning/slides/chapter06.pdf Page/slide: 9
        #Interference: one deletes a precondition of the other 

        #to check if there is Interference at those nodes
        #we get actions adding and removing effects
        action_a1 = node_a1.action
        action_a2 = node_a2.action

        #getting removing effect from both actions
        rem_a1 = action_a1.effect_rem
        rem_a2 = action_a2.effect_rem

        #getting positive preconditions for botha ctions
        pre_a1 = action_a1.precond_pos
        pre_a2 = action_a2.precond_pos

        #checking if removing state of action is inside of positive preconditins (deletes it)]
        #if yes they are mutax
        for rem_ in rem_a1:
            if rem_ in pre_a2:
                return True

        for rem_ in rem_a2:
            if rem_ in pre_a1:
                return True

        return False

    def competing_needs_mutex(self, node_a1: PgNode_a, node_a2: PgNode_a) -> bool:
        """
        Test a pair of actions for mutual exclusion, returning True if one of
        the precondition of one action is mutex with a precondition of the
        other action.

        :param node_a1: PgNode_a
        :param node_a2: PgNode_a
        :return: bool
        """
        #Slides to find more inforumation: University of Maryland https://www.cs.umd.edu/~nau/planning/slides/chapter06.pdf Page/slide: 9
        #Competing needs: they have mutually exclusive preconditions

        #getting parents of both NODES
        parents_a1 = node_a1.parents
        parents_a2 = node_a2.parents

        #checking if some of parents are mutax, if yes we return True
        for parent_a1 in parents_a1:
            for parent_a2 in parents_a2:
                if parent_a1.is_mutex(parent_a2):
                    return True 

        #This is code for other direction, but it is not necessary
        # for parent_a2 in parents_a2:
        #     for parent_a1 in parents_a1:
        #         if parent_a2.is_mutex(parent_a1):
        #             return True 
    
        
        return False

    def update_s_mutex(self, nodeset: set):
        """ Determine and update sibling mutual exclusion for S-level nodes

        Mutex action tests section from 3rd Ed. 10.3 or 2nd Ed. 11.4
        A mutex relation holds between literals at a given level
        if either of the two conditions hold between the pair:
           Negation
           Inconsistent support

        :param nodeset: set of PgNode_a (siblings in the same level)
        :return:
            mutex set in each PgNode_a in the set is appropriately updated
        """
        nodelist = list(nodeset)
        for i, n1 in enumerate(nodelist[:-1]):
            for n2 in nodelist[i + 1:]:
                if self.negation_mutex(n1, n2) or self.inconsistent_support_mutex(n1, n2):
                    mutexify(n1, n2)

    def negation_mutex(self, node_s1: PgNode_s, node_s2: PgNode_s) -> bool:
        """
        Test a pair of state literals for mutual exclusion, returning True if
        one node is the negation of the other, and False otherwise.

        HINT: Look at the PgNode_s.__eq__ defines the notion of equivalence for
        literal expression nodes, and the class tracks whether the literal is
        positive or negative.

        :param node_s1: PgNode_s
        :param node_s2: PgNode_s
        :return: bool
        """
        #Slides to find more inforumation: University of Maryland https://www.cs.umd.edu/~nau/planning/slides/chapter06.pdf Page/slide: 9
        #If both nodes have same sybol but one is negative and another is positive, they are negation of one another

        #this method is created similary to __eq__ function in PhNode_s
        #it takes two nodes and returns true if both of ndoes have same symbol both different polarity (positive, negative)
        def negation(node_1, node_2):
            #Templete used from __eq__ function from PhNode_s class above
            return(node_1.is_pos != node_2.is_pos and node_1.symbol == node_2.symbol)
            
        #Return result of negation function -> True or False
        return negation(node_s1, node_s2)

    def inconsistent_support_mutex(self, node_s1: PgNode_s, node_s2: PgNode_s):
        """
        Test a pair of state literals for mutual exclusion, returning True if
        there are no actions that could achieve the two literals at the same
        time, and False otherwise.  In other words, the two literal nodes are
        mutex if all of the actions that could achieve the first literal node
        are pairwise mutually exclusive with all of the actions that could
        achieve the second literal node.

        HINT: The PgNode.is_mutex method can be used to test whether two nodes
        are mutually exclusive.

        :param node_s1: PgNode_s
        :param node_s2: PgNode_s
        :return: bool
        """
        #https://www.cs.umd.edu/~nau/planning/slides/chapter06.pdf
        #The intuition behind incosistent_support is -  We have some state nodes in s layer/level
        #after performing those we have some actions in a action layer. If those actions are mutax (negate on another)
        #Those nodes in state layers are mutax as well.
        
        #getting parents of both nodes
        parents_a1 = node_s1.parents
        parents_a2 = node_s2.parents

        #counter of mutax pairs set to 0
        counter_of_mutex = 0

        #For each parent from a first node we are checking all nodes in parent states from second node
        for parent_a1 in parents_a1:
            for parent_a2 in parents_a2:
                if parent_a1.is_mutex(parent_a2):
                    #if those two parents are mutax we are adding +1 to our counter
                    counter_of_mutex += 1

        #if counter_of_mutax is the same of parents for first node those two node are incosistent
        if counter_of_mutex == len(parents_a1):
            return True

        return False

    def h_levelsum(self) -> int:
        """The sum of the level costs of the individual goals (admissible if goals independent)

        :return: int
        """

        #Defining starting variables

        #NODE: I am calling levels, leyers, because of the structure of  a Planning Graph, it looks like Neural network :)
        level_sum = 0
        goals = self.problem.goal
        num_of_layers = len(self.s_levels)
          
        # TODO implement
        # for each goal in the problem, determine the level cost, then add them together

        #define gola_checked list which is important so we don't check same goal on different levels
        #We will get result for lowest level which have goal inside 
        goal_checked = []

        #iterating for each level
        for layer_index in range(num_of_layers):
            #getting nodes/states inside current looked level
            current_level_states = self.s_levels[layer_index]
            #boolean checker to break from loop if we find goal
            goal_check = False
            #going through all nodes in current level
            for node in current_level_states:

                #checking for each goal that we have in our problem 
                #is it inside of current level
                for goal in goals:
                    #if current node is a goal
                    if node.symbol == goal:
                        #But we should not have goal inside goals that we have already checked
                        if not goal in goal_checked:
                            #adding it to checked goals
                            goal_checked.append(goal)
                            goal_check = True
                            #increasing lelve_sum by index of a current level/layer
                            level_sum += layer_index
                            break

                if goal_check:
                    break

        
        return level_sum
