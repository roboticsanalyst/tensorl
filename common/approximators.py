'''
This file contains various types of function approximators.
The approximator can have multiple input (x) and output (self.output).
For instance, you may want to run Q(s,a) and Q(s,pi(s)) on the same network, sharing
the placeholders and having a single graph to easily define cost functions and compute their derivatives.
To this end, the input x of the MLP is a list of placeholders, and the resulting output will be a list as well.

Exampe: to define an approximator for the Q-fuction that is able to run both Q(s,a) and Q(s,pi(s)),
create an MLP with x = [tf.concat([s, a], axis=1), tf.concat([s, pi(s)], axis=1)].
Then, self.output[0] will be the tensor representing Q(s,a), while self.output[1] will represent Q(s,pi(s)).

Linear approximators y = theta * phi(x) also have an attribute for features phi.
For MLP, this would correspond to the derivative of the network output w.r.t. the network parameters,
but tf.gradients automatically computes the mean of the gradients, so you have to manually loop over all samples.
'''

import tensorflow as tf
import numpy as np


class MLP:
    '''
    Multi-layer perceptron.
    '''
    def __init__(self, x, sizes, activations, scope, keep_prob=None):
        self.name = 'mlp_approx_' + scope
        self.keep_prob = keep_prob
        with tf.variable_scope(scope):
            self.output = []
            for i in x:
                last_out = i
                for l, size in enumerate(sizes):
                    last_out = tf.layers.dense(last_out, size, activation=activations[l], name=str(l), reuse=tf.AUTO_REUSE)
                    if keep_prob is not None:
                        last_out = tf.nn.dropout(last_out, keep_prob=keep_prob)
                self.output.append(last_out)
        self.vars = tf.trainable_variables(scope=scope)


    def reset(self, session, value=0.):
        new_lin = tf.Variable(1e-8*(np.random.rand(self.vars[-2].shape[0],self.vars[-2].shape[1])-0.5),dtype=self.output[0].dtype) # set linear weights to ~0
        new_bias = tf.Variable(value*np.ones(shape=self.vars[-1].shape),dtype=self.output[0].dtype) # set bias to desired value
        session.run(tf.variables_initializer([new_lin, new_bias]))
        session.run(self.vars[-2].assign(new_lin))
        session.run(self.vars[-1].assign(new_bias))

    def size(self):
        return sum([np.prod(y) for y in [x.get_shape().as_list() for x in self.vars]])


class Quadratic:
    '''
    Linear approximator with quadratic features.
    '''
    def __init__(self, x, size, scope):
        self.name = 'quadratic_approx_' + scope
        with tf.variable_scope(scope):
            self.output = []
            self.phi = []
            for i in x:
                x_size = i.get_shape().as_list()[1]
                last_out = tf.concat([1.0+0*i[:,:1], i], axis=1)
                last_out = [last_out[:,k]*last_out[:,j] for k in range(x_size+1) for j in range(k,x_size+1)]
                last_out = tf.stack(last_out,1)
                self.phi.append(last_out)
                last_out = tf.layers.dense(last_out, size, activation=None, name=str(0), use_bias=False, reuse=tf.AUTO_REUSE)
                self.output.append(last_out)
        self.vars = tf.trainable_variables(scope=scope)

    def reset(self, session, value=0.):
        new_val = 1e-8*(np.random.rand(self.vars[0].shape[0],self.vars[0].shape[1])-0.5); # set linear+bias weights to 0
        new_val[0] = value # set bias weight to desired value
        new_vars = tf.Variable(new_val, dtype=self.output[0].dtype)
        session.run(tf.variables_initializer([new_vars]))
        session.run(self.vars[0].assign(new_vars))

    def size(self):
        return sum([np.prod(y) for y in [x.get_shape().as_list() for x in self.vars]])



class Linear:
    '''
    Linear approximator.
    '''
    def __init__(self, x, size, scope, use_bias=True):
        self.name = 'linear_approx_' + scope
        with tf.variable_scope(scope):
            self.output = []
            self.phi = []
            for i in x:
                last_out = i
                self.phi.append(last_out)
                last_out = tf.layers.dense(last_out, size, activation=None, name=str(0), use_bias=use_bias, reuse=tf.AUTO_REUSE)
                self.output.append(last_out)
        self.vars = tf.trainable_variables(scope=scope)

    def reset(self, session, value=0.):
        if len(self.vars) == 2:
            new_lin = tf.Variable(1e-8*(np.random.rand(self.vars[-2].shape[0],self.vars[-2].shape[1])-0.5),dtype=self.output[0].dtype) # set linear weights to ~0
            new_bias = tf.Variable(value*np.ones(shape=self.vars[-1].shape),dtype=self.output[0].dtype) # set bias to desired value
            session.run(tf.variables_initializer([new_lin, new_bias]))
            session.run(self.vars[-2].assign(new_lin))
            session.run(self.vars[-1].assign(new_bias))
        else:
            new_lin = tf.Variable(1e-8*(np.random.rand(self.vars[-1].shape[0],self.vars[-1].shape[1])-0.5),dtype=self.output[0].dtype)
            session.run(tf.variables_initializer([new_lin]))
            session.run(self.vars[-1].assign(new_lin))

    def size(self):
        return sum([np.prod(y) for y in [x.get_shape().as_list() for x in self.vars]])



class Fourier:
    '''
    Linear approximator with random Fuorier features.
    Bandwidth can be a list of the size of the x (one bandwidth per input).
    '''
    def __init__(self, x, size, n_feat, scope, bandwidth=0.3):
        self.name = 'fourier_approx_' + scope
        n_x = x[0].get_shape().as_list()[1]
        self.P = tf.constant(np.random.normal(0., 1., (n_x, n_feat)), dtype=x[0].dtype)
        self.shift = tf.constant(np.random.uniform(-np.pi, np.pi, (n_feat,)), dtype=x[0].dtype)
        self.bandwidth = bandwidth

        with tf.variable_scope(scope):
            theta = tf.Variable(tf.random_normal([n_feat+1,size], dtype=x[0].dtype))
            self.output = []
            self.phi = []
            for i in x:
                phi = tf.sin(tf.matmul(i/self.bandwidth,self.P) + self.shift)
                phi = tf.concat([1.0+0*i[:,:1], phi], axis=1) # add bias
                self.phi.append(phi)
                self.output.append(tf.matmul(phi, theta))
        self.vars = tf.trainable_variables(scope=scope)

    def reset(self, session, value=0.):
        new_val = 1e-8*(np.random.rand(self.vars[0].shape[0],self.vars[0].shape[1])-0.5); # set linear+bias weights to 0
        new_val[0] = value # set bias weight to desired value
        new_vars = tf.Variable(new_val, dtype=self.output[0].dtype)
        session.run(tf.variables_initializer([new_vars]))
        session.run(self.vars[0].assign(new_vars))

    def size(self):
        return sum([np.prod(y) for y in [x.get_shape().as_list() for x in self.vars]])



class RFB:
    '''
    Linear approximator with radial basis functions
    phi(x) = exp( -(x - centers)' * B * (x - centers) )
    where B is a diagonal matrix denoting the bandwiths of the Gaussians.
    Centers are uniformly placed over x space, and bandwidths are automatically computed.
    '''
    def __init__(self, x, size, n_centers, x_space, scope):
        self.name = 'rbf_approx_' + scope
        n_x = x[0].get_shape().as_list()[1]
        self.B = np.sqrt(n_centers**2 / np.diff(x_space)**2).T # bandwiths
        m = np.diff(x_space) / n_centers
        tmp = []
        for i in range(n_x): # automatically place centers
            tmp.append(np.linspace(-m[i]*0.1+x_space[i][0], x_space[i][1]+m[i]*0.1, n_centers))
        tmp = np.meshgrid(*tmp)
        self.centers = np.zeros((n_centers**n_x, n_x))
        for i in range(n_x):
            self.centers[:,i] = tmp[i].flatten()

        with tf.variable_scope(scope):
            theta = tf.Variable(tf.random_normal([self.centers.shape[0]+1,size], dtype=x[0].dtype))
            self.output = []
            self.phi = []
            cB = self.centers * self.B
            for i in x:
                xB = i * self.B
                phi = tf.exp(-tf.reduce_sum((tf.expand_dims(xB, axis=2) - np.expand_dims(cB.T, axis=0))**2, axis=1))
                phi = tf.concat([1.0+0*i[:,:1], phi], axis=1) # add bias
                self.phi.append(phi)
                self.output.append(tf.matmul(phi, theta))
        self.vars = tf.trainable_variables(scope=scope)

    def reset(self, session, value=0.):
        new_val = 1e-8*(np.random.rand(self.vars[0].shape[0],self.vars[0].shape[1])-0.5); # set linear+bias weights to 0
        new_val[0] = value # set bias weight to desired value
        new_vars = tf.Variable(new_val, dtype=self.output[0].dtype)
        session.run(tf.variables_initializer([new_vars]))
        session.run(self.vars[0].assign(new_vars))

    def size(self):
        return sum([np.prod(y) for y in [x.get_shape().as_list() for x in self.vars]])
